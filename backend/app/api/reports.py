from datetime import date, datetime, time, timedelta
from io import BytesIO
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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


def _financial_data(period, start_date, end_date, station_id, user, db):
    start, end = _period_dates(period, start_date, end_date)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)
    tickets = _scope(db.query(Ticket), Ticket, user, station_id).filter(
        func.date(Ticket.created_at) >= start, func.date(Ticket.created_at) <= end
    ).order_by(Ticket.created_at.asc()).all()
    revenue = sum(t.total for t in tickets)
    collected = int(_scope(db.query(Payment), Payment, user, station_id).filter(
        Payment.created_at >= start_dt, Payment.created_at <= end_dt
    ).with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0)

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
    ).order_by(Expense.expense_date.asc()).all()
    expense_ids = [e.id for e in expenses]
    committed = sum(e.amount for e in expenses)
    expense_paid_q = db.query(ExpensePayment).filter(
        ExpensePayment.company_id == user.company_id,
        ExpensePayment.paid_at >= start_dt, ExpensePayment.paid_at <= end_dt
    )
    if user.station_id is not None:
        expense_paid_q = expense_paid_q.filter(ExpensePayment.station_id == user.station_id)
    elif station_id is not None:
        expense_paid_q = expense_paid_q.filter(ExpensePayment.station_id == station_id)
    disbursements = int(expense_paid_q.with_entities(func.coalesce(func.sum(ExpensePayment.amount), 0)).scalar() or 0)

    paid_by_expense = {}
    if expense_ids:
        rows = db.query(ExpensePayment.expense_id, func.sum(ExpensePayment.amount)).filter(
            ExpensePayment.company_id == user.company_id, ExpensePayment.expense_id.in_(expense_ids)
        ).group_by(ExpensePayment.expense_id).all()
        paid_by_expense = {eid: int(amount or 0) for eid, amount in rows}
    expense_liabilities = sum(max(e.amount - paid_by_expense.get(e.id, 0), 0) for e in expenses)

    assets = _scope(db.query(FixedAsset), FixedAsset, user, station_id).all()
    depreciation = 0
    before = start - timedelta(days=1)
    for asset in assets:
        if asset.status == "active":
            depreciation += max(_asset_accumulated(asset, end) - _asset_accumulated(asset, before), 0)

    return {
        "period": period, "start_date": start, "end_date": end, "station_id": station_id or user.station_id,
        "currency": "XOF", "revenue": revenue, "collections": collected,
        "receivables_outstanding": receivables, "expenses_committed": committed,
        "expense_disbursements": disbursements, "expense_liabilities_for_period": expense_liabilities,
        "depreciation_charge": depreciation, "simplified_management_result": revenue - committed - depreciation,
        "net_cash_flow": collected - disbursements, "tickets_count": len(tickets),
        "expenses_count": len(expenses), "assets_count": len(assets),
        "notes": [
            "Le chiffre d'affaires correspond aux tickets créés pendant la période.",
            "Les encaissements et décaissements correspondent aux règlements réellement enregistrés pendant la période.",
            "Les créances clients sont le solde impayé de tous les tickets visibles à la date du rapport.",
            "Les dettes de charges correspondent au solde des dépenses engagées pendant la période.",
            "Le résultat est un indicateur simplifié de gestion, non une comptabilité générale certifiée.",
            "Le flux net ne constitue pas un solde bancaire ou de caisse : les fonds initiaux et autres mouvements ne sont pas inclus."
        ]
    }, tickets, expenses


@router.get("/reports/financial")
def financial_report(
    period: Literal["day", "week", "month", "year", "custom"] = "month",
    start_date: date | None = None, end_date: date | None = None,
    station_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    data, _, _ = _financial_data(period, start_date, end_date, station_id, user, db)
    return data


@router.get("/reports/financial/export")
def export_financial_report(
    format: Literal["pdf", "xlsx"] = "pdf",
    period: Literal["day", "week", "month", "year", "custom"] = "month",
    start_date: date | None = None, end_date: date | None = None,
    station_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    data, tickets, expenses = _financial_data(period, start_date, end_date, station_id, user, db)
    company = db.query(Station).filter(Station.company_id == user.company_id)
    if data["station_id"] is not None:
        company = company.filter(Station.id == data["station_id"])
    station = company.first()
    station_label = station.name if station else "Toutes les stations"
    filename = f"rapport_financier_{data['start_date']}_{data['end_date']}"

    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        workbook = Workbook()
        summary = workbook.active
        summary.title = "Synthèse"
        summary.append(["AUTO LAVAGE MANAGER - RAPPORT FINANCIER"])
        summary.append(["Période", str(data["start_date"]), "au", str(data["end_date"])])
        summary.append(["Station", station_label])
        summary.append(["Indicateur", "Montant (FCFA)"])
        labels = [
            ("Chiffre d'affaires", "revenue"), ("Encaissements", "collections"),
            ("Créances clients", "receivables_outstanding"), ("Charges engagées", "expenses_committed"),
            ("Décaissements", "expense_disbursements"), ("Dettes de charges", "expense_liabilities_for_period"),
            ("Dotations aux amortissements", "depreciation_charge"),
            ("Résultat simplifié de gestion", "simplified_management_result"), ("Flux net de la période", "net_cash_flow")
        ]
        for label, key in labels:
            summary.append([label, data[key]])
        summary.append([])
        summary.append(["Note", "Le résultat est un indicateur simplifié et ne constitue pas une comptabilité certifiée."])
        summary.append(["Note", "Le flux net n'est pas un solde bancaire ou de caisse."])
        tickets_ws = workbook.create_sheet("Tickets")
        tickets_ws.append(["Date", "N° ticket", "Client", "Véhicule", "Statut", "Total FCFA"])
        for ticket in tickets:
            tickets_ws.append([ticket.created_at.replace(tzinfo=None) if ticket.created_at else None,
                ticket.ticket_number, ticket.customer_name or "", ticket.vehicle_type, ticket.status, ticket.total])
        expenses_ws = workbook.create_sheet("Dépenses")
        expenses_ws.append(["Date", "Catégorie", "Libellé", "Fournisseur", "Montant FCFA"])
        for expense in expenses:
            expenses_ws.append([expense.expense_date, expense.category, expense.label, expense.vendor or "", expense.amount])
        for ws in workbook.worksheets:
            ws.freeze_panes = "A4" if ws.title == "Synthèse" else "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="174A6E")
            for column in ws.columns:
                width = min(max(max(len(str(c.value or "")) for c in column) + 2, 12), 48)
                ws.column_dimensions[get_column_letter(column[0].column)].width = width
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(vertical="center")
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'})

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("AUTO LAVAGE MANAGER", styles["Title"]),
        Paragraph("Rapport financier de gestion", styles["Heading2"]),
        Paragraph(f"Période : {data['start_date']} au {data['end_date']} | {station_label}", styles["Normal"]),
        Spacer(1, 8*mm)]
    rows = [["Indicateur", "Montant (FCFA)"]]
    for label, key in [
        ("Chiffre d'affaires", "revenue"), ("Encaissements", "collections"),
        ("Créances clients", "receivables_outstanding"), ("Charges engagées", "expenses_committed"),
        ("Décaissements", "expense_disbursements"), ("Dettes de charges", "expense_liabilities_for_period"),
        ("Dotations aux amortissements", "depreciation_charge"),
        ("Résultat simplifié de gestion", "simplified_management_result"), ("Flux net de la période", "net_cash_flow")
    ]:
        rows.append([label, f"{data[key]:,}".replace(",", " ")])
    table = Table(rows, colWidths=[105*mm, 55*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174A6E")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#D8E2E9")),("PADDING",(0,0),(-1,-1),7),
        ("ALIGN",(1,1),(1,-1),"RIGHT")]))
    story += [table, Spacer(1, 6*mm), Paragraph("Détail des tickets", styles["Heading2"])]
    ticket_rows = [["Date", "Ticket", "Client", "Montant"]]
    for t in tickets[:100]:
        ticket_rows.append([str(t.created_at.date()) if t.created_at else "", t.ticket_number,
            (t.customer_name or "Client comptoir")[:24], f"{t.total:,}".replace(",", " ")])
    if len(ticket_rows) == 1:
        ticket_rows.append(["—", "Aucun ticket", "—", "0"])
    tt = Table(ticket_rows, colWidths=[27*mm, 48*mm, 50*mm, 35*mm], repeatRows=1)
    tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E7F0F6")),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D8E2E9")),("FONTSIZE",(0,0),(-1,-1),8),
        ("PADDING",(0,0),(-1,-1),5)]))
    story += [tt, Spacer(1, 5*mm), Paragraph("Détail des dépenses", styles["Heading2"])]
    expense_rows = [["Date", "Catégorie", "Libellé", "Montant"]]
    for e in expenses[:100]:
        expense_rows.append([str(e.expense_date), e.category, e.label[:28], f"{e.amount:,}".replace(",", " ")])
    if len(expense_rows) == 1:
        expense_rows.append(["—", "—", "Aucune dépense", "0"])
    et = Table(expense_rows, colWidths=[25*mm, 35*mm, 65*mm, 35*mm], repeatRows=1)
    et.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E7F0F6")),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D8E2E9")),("FONTSIZE",(0,0),(-1,-1),8),
        ("PADDING",(0,0),(-1,-1),5)]))
    story += [et, Spacer(1, 5*mm), Paragraph(
        "Attention : résultat simplifié de gestion, non certifié. Le flux net ne représente pas le solde réel de caisse ou de banque.",
        styles["Italic"])]
    doc.build(story)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
