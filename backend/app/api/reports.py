from datetime import date, datetime, time, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Expense, ExpensePayment, FixedAsset, Payment, Station, Ticket, User

router = APIRouter()


def _period_dates(period: str, start_date: date | None, end_date: date | None):
    today = date.today()
    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(422, "Les dates de début et de fin sont obligatoires pour une période personnalisée")
        start, end = start_date, end_date
    elif period == "day":
        start = end = today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = today.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    elif period == "year":
        start, end = today.replace(month=1, day=1), today.replace(month=12, day=31)
    else:
        raise HTTPException(422, "Période non reconnue")
    if start > end:
        raise HTTPException(422, "La date de début doit précéder la date de fin")
    return start, end


def _scope(query, model, user: User, station_id: int | None):
    query = query.filter(model.company_id == user.company_id)
    if user.station_id is not None:
        query = query.filter(model.station_id == user.station_id)
    elif station_id is not None:
        station = query.session.query(Station).filter(
            Station.id == station_id, Station.company_id == user.company_id
        ).first()
        if station is None:
            raise HTTPException(404, "Station introuvable dans votre entreprise")
        query = query.filter(model.station_id == station_id)
    return query


def _asset_accumulated(asset: FixedAsset, cutoff: date) -> int:
    if cutoff < asset.in_service_date:
        months = 0
    else:
        months = (cutoff.year - asset.in_service_date.year) * 12 + cutoff.month - asset.in_service_date.month + 1
    months = min(max(months, 0), asset.useful_life_months)
    return round((asset.acquisition_cost - asset.residual_value) * months / asset.useful_life_months)


@router.get("/reports/financial")
def financial_report(
    period: Literal["day", "week", "month", "year", "custom"] = "month",
    start_date: date | None = None,
    end_date: date | None = None,
    station_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _period_dates(period, start_date, end_date)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)

    tickets = _scope(db.query(Ticket), Ticket, user, station_id).filter(
        func.date(Ticket.created_at) >= start, func.date(Ticket.created_at) <= end
    ).all()
    ticket_ids = [t.id for t in tickets]
    revenue = sum(t.total for t in tickets)
    ticket_payments_q = _scope(db.query(Payment), Payment, user, station_id).filter(
        Payment.created_at >= start_dt, Payment.created_at <= end_dt
    )
    collected = int(ticket_payments_q.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0)

    # Outstanding customer balances are a point-in-time balance, not period cash receipts.
    all_tickets = _scope(db.query(Ticket), Ticket, user, station_id).all()
    all_ticket_ids = [t.id for t in all_tickets]
    paid_by_ticket = {}
    if all_ticket_ids:
        rows = db.query(Payment.ticket_id, func.sum(Payment.amount)).filter(
            Payment.company_id == user.company_id, Payment.ticket_id.in_(all_ticket_ids)
        ).group_by(Payment.ticket_id).all()
        paid_by_ticket = {ticket_id: int(amount or 0) for ticket_id, amount in rows}
    receivables = sum(max(t.total - paid_by_ticket.get(t.id, 0), 0) for t in all_tickets)

    expenses = _scope(db.query(Expense), Expense, user, station_id).filter(
        Expense.expense_date >= start, Expense.expense_date <= end
    ).all()
    expense_ids = [e.id for e in expenses]
    committed = sum(e.amount for e in expenses)
    expense_paid_in_period_q = db.query(ExpensePayment).filter(
        ExpensePayment.company_id == user.company_id,
        ExpensePayment.paid_at >= start_dt, ExpensePayment.paid_at <= end_dt
    )
    if user.station_id is not None:
        expense_paid_in_period_q = expense_paid_in_period_q.filter(ExpensePayment.station_id == user.station_id)
    elif station_id is not None:
        expense_paid_in_period_q = expense_paid_in_period_q.filter(ExpensePayment.station_id == station_id)
    disbursements = int(expense_paid_in_period_q.with_entities(
        func.coalesce(func.sum(ExpensePayment.amount), 0)
    ).scalar() or 0)

    expense_paid_by_id = {}
    if expense_ids:
        rows = db.query(ExpensePayment.expense_id, func.sum(ExpensePayment.amount)).filter(
            ExpensePayment.company_id == user.company_id,
            ExpensePayment.expense_id.in_(expense_ids)
        ).group_by(ExpensePayment.expense_id).all()
        expense_paid_by_id = {expense_id: int(amount or 0) for expense_id, amount in rows}
    expense_payments_total = sum(expense_paid_by_id.values())
    expense_liabilities = sum(max(e.amount - expense_paid_by_id.get(e.id, 0), 0) for e in expenses)

    assets = _scope(db.query(FixedAsset), FixedAsset, user, station_id).all()
    depreciation = 0
    for asset in assets:
        if asset.status != "active":
            continue
        before = start - timedelta(days=1)
        depreciation += max(_asset_accumulated(asset, end) - _asset_accumulated(asset, before), 0)

    # The simplified management result uses expenses committed in the selected period,
    # plus the depreciation charge for that period. It is not statutory accounting.
    result = revenue - committed - depreciation
    return {
        "period": period, "start_date": start, "end_date": end, "station_id": station_id or user.station_id,
        "currency": "XOF",
        "revenue": revenue,
        "collections": collected,
        "receivables_outstanding": receivables,
        "expenses_committed": committed,
        "expense_disbursements": disbursements,
        "expense_liabilities_for_period": expense_liabilities,
        "depreciation_charge": depreciation,
        "simplified_management_result": result,
        "net_cash_flow": collected - disbursements,
        "tickets_count": len(tickets),
        "expenses_count": len(expenses),
        "assets_count": len(assets),
        "notes": [
            "Le chiffre d'affaires correspond aux tickets créés pendant la période.",
            "Les encaissements et décaissements correspondent aux règlements réellement enregistrés pendant la période.",
            "Les créances clients sont le solde impayé de tous les tickets visibles à la date du rapport.",
            "Les dettes de charges correspondent au solde des dépenses engagées pendant la période.",
            "Le résultat est un indicateur simplifié de gestion, non une comptabilité générale certifiée.",
            "Le flux net ne constitue pas un solde bancaire ou de caisse : les fonds initiaux et autres mouvements ne sont pas inclus."
        ]
    }
