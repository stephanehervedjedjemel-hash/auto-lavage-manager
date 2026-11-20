from datetime import date, datetime, time, timedelta
from io import BytesIO
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Expense, ExpensePayment, FixedAsset, Payment, TicketRefund, Station, Ticket, User

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
    revenue = sum(t.total for t in tickets if t.status != "cancelled")
    collected_gross = int(_scope(db.query(Payment), Payment, user, station_id).filter(
        Payment.created_at >= start_dt, Payment.created_at <= end_dt
    ).with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0)
    refunds_q = _scope(db.query(TicketRefund), TicketRefund, user, station_id).filter(
        TicketRefund.refunded_at >= start_dt, TicketRefund.refunded_at <= end_dt
    )
    refunds_total = int(refunds_q.with_entities(func.coalesce(func.sum(TicketRefund.amount), 0)).scalar() or 0)
    collected = collected_gross - refunds_total

    all_tickets = _scope(db.query(Ticket), Ticket, user, station_id).filter(Ticket.status != "cancelled").all()
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
        "currency": "XOF", "revenue": revenue, "collections": collected, "refunds_total": refunds_total,
        "receivables_outstanding": receivables, "expenses_committed": committed,
        "expense_disbursements": disbursements, "expense_liabilities_for_period": expense_liabilities,
        "depreciation_charge": depreciation, "simplified_management_result": revenue - committed - depreciation,
        "net_cash_flow": collected - disbursements, "tickets_count": sum(1 for t in tickets if t.status != "cancelled"),
        "expenses_count": len(expenses), "assets_count": len(assets),
        "notes": [
            "Le chiffre d'affaires correspond aux tickets créés pendant la période.",
            "Les encaissements sont nets des remboursements enregistrés pendant la période.",
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
            ("Chiffre d'affaires", "revenue"), ("Encaissements nets", "collections"), ("Remboursements", "refunds_total"),
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
        ("Chiffre d'affaires", "revenue"), ("Encaissements nets", "collections"), ("Remboursements", "refunds_total"),
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


@router.get("/reports/stations")
def station_profitability_report(
    period: Literal["day", "week", "month", "year", "custom"] = "month",
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare les indicateurs financiers des stations visibles par l'utilisateur."""
    start, end = _period_dates(period, start_date, end_date)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)

    stations_query = db.query(Station).filter(
        Station.company_id == user.company_id,
        Station.is_active.is_(True),
    )
    if user.station_id is not None:
        stations_query = stations_query.filter(Station.id == user.station_id)
    stations = stations_query.order_by(Station.name.asc()).all()

    results = []
    for station in stations:
        tickets = db.query(Ticket).filter(
            Ticket.company_id == user.company_id,
            Ticket.station_id == station.id,
            func.date(Ticket.created_at) >= start,
            func.date(Ticket.created_at) <= end,
        ).all()
        revenue = sum(ticket.total for ticket in tickets if ticket.status != "cancelled")

        collections_gross = int(db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.company_id == user.company_id,
            Payment.station_id == station.id,
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
        ).scalar() or 0)
        refunds_total = int(db.query(func.coalesce(func.sum(TicketRefund.amount), 0)).filter(
            TicketRefund.company_id == user.company_id,
            TicketRefund.station_id == station.id,
            TicketRefund.refunded_at >= start_dt,
            TicketRefund.refunded_at <= end_dt,
        ).scalar() or 0)
        collections = collections_gross - refunds_total

        expenses = db.query(Expense).filter(
            Expense.company_id == user.company_id,
            Expense.station_id == station.id,
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        ).all()
        committed = sum(expense.amount for expense in expenses)

        disbursements = int(db.query(func.coalesce(func.sum(ExpensePayment.amount), 0)).filter(
            ExpensePayment.company_id == user.company_id,
            ExpensePayment.station_id == station.id,
            ExpensePayment.paid_at >= start_dt,
            ExpensePayment.paid_at <= end_dt,
        ).scalar() or 0)

        assets = db.query(FixedAsset).filter(
            FixedAsset.company_id == user.company_id,
            FixedAsset.station_id == station.id,
            FixedAsset.status == "active",
        ).all()
        before = start - timedelta(days=1)
        depreciation = sum(
            max(_asset_accumulated(asset, end) - _asset_accumulated(asset, before), 0)
            for asset in assets
        )

        results.append({
            "station_id": station.id,
            "station_name": station.name,
            "station_code": station.code,
            "tickets_count": sum(1 for ticket in tickets if ticket.status != "cancelled"),
            "revenue": revenue,
            "collections": collections,
            "refunds_total": refunds_total,
            "expenses_committed": committed,
            "expense_disbursements": disbursements,
            "depreciation_charge": depreciation,
            "simplified_management_result": revenue - committed - depreciation,
            "net_cash_flow": collections - disbursements,
            "assets_count": len(assets),
            "asset_net_book_value": sum(
                max(asset.acquisition_cost - _asset_accumulated(asset, end), asset.residual_value)
                for asset in assets
            ),
        })

    return {
        "period": period,
        "start_date": start,
        "end_date": end,
        "currency": "XOF",
        "stations_count": len(results),
        "stations": results,
        "notes": [
            "Le résultat simplifié correspond au chiffre d'affaires moins les charges engagées et les dotations aux amortissements.",
            "Le flux net correspond aux encaissements moins les décaissements de dépenses ; il ne représente pas un solde de caisse ou bancaire.",
            "Les immobilisations partagées entre plusieurs stations ne sont pas réparties automatiquement.",
            "Les indicateurs sont des données de gestion et ne constituent pas une comptabilité certifiée.",
        ],
    }


def _asset_register_rows(as_of, station_id, user, db):
    query = db.query(FixedAsset, Station.name).join(Station, Station.id == FixedAsset.station_id).filter(
        FixedAsset.company_id == user.company_id,
        Station.company_id == user.company_id,
    )
    if user.station_id is not None:
        query = query.filter(FixedAsset.station_id == user.station_id)
    elif station_id is not None:
        station = db.query(Station).filter(
            Station.id == station_id, Station.company_id == user.company_id
        ).first()
        if station is None:
            raise HTTPException(404, "Station introuvable dans votre entreprise")
        query = query.filter(FixedAsset.station_id == station_id)
    rows = []
    for asset, station_name in query.order_by(FixedAsset.acquisition_date.asc(), FixedAsset.asset_code.asc()).limit(2000).all():
        values = _asset_accumulated(asset, as_of)
        months = 0 if as_of < asset.in_service_date else (
            (as_of.year - asset.in_service_date.year) * 12 + as_of.month - asset.in_service_date.month + 1
        )
        months = min(max(months, 0), asset.useful_life_months)
        monthly = round((asset.acquisition_cost - asset.residual_value) / asset.useful_life_months)
        rows.append({
            "asset_code": asset.asset_code, "name": asset.name, "category": asset.category,
            "station": station_name, "supplier": asset.supplier or "",
            "acquisition_date": asset.acquisition_date, "in_service_date": asset.in_service_date,
            "acquisition_cost": asset.acquisition_cost, "residual_value": asset.residual_value,
            "useful_life_months": asset.useful_life_months, "depreciation_months": months,
            "monthly_depreciation": monthly, "accumulated_depreciation": values,
            "net_book_value": max(asset.acquisition_cost - values, asset.residual_value),
            "status": asset.status,
        })
    return rows


@router.get("/assets/export")
def export_asset_register(
    format: Literal["pdf", "xlsx"] = "xlsx",
    as_of: date | None = None,
    station_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cutoff = as_of or date.today()
    rows = _asset_register_rows(cutoff, station_id, user, db)
    filename = f"registre_immobilisations_{cutoff}"
    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        workbook = Workbook()
        ws = workbook.active
        ws.title = "Immobilisations"
        ws.append(["Code", "Désignation", "Catégorie", "Station", "Fournisseur",
            "Acquisition", "Mise en service", "Coût acquisition (FCFA)", "Valeur résiduelle (FCFA)",
            "Durée (mois)", "Mois amortis", "Dotation mensuelle (FCFA)",
            "Amortissements cumulés (FCFA)", "VNC (FCFA)", "Statut"])
        for row in rows:
            ws.append([row["asset_code"], row["name"], row["category"], row["station"], row["supplier"],
                row["acquisition_date"], row["in_service_date"], row["acquisition_cost"], row["residual_value"],
                row["useful_life_months"], row["depreciation_months"], row["monthly_depreciation"],
                row["accumulated_depreciation"], row["net_book_value"], row["status"]])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="174A6E")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[1].height = 34
        for column in ws.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 32)
            ws.column_dimensions[get_column_letter(column[0].column)].width = width
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return StreamingResponse(output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'})

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=8*mm, leftMargin=8*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("AUTO LAVAGE MANAGER — REGISTRE DES IMMOBILISATIONS", styles["Title"]),
        Paragraph(f"Situation des amortissements au {cutoff} · {len(rows)} immobilisation(s)", styles["Normal"]),
        Spacer(1, 5*mm)]
    table_rows = [["Code / Désignation", "Station", "Acquisition", "Coût", "Résiduelle",
        "Durée", "Mois", "Amort. cumulés", "VNC"]]
    for row in rows:
        table_rows.append([
            Paragraph(f"{row['asset_code']}<br/>{row['name'][:38]}", styles["BodyText"]),
            row["station"][:20], str(row["acquisition_date"]),
            f"{row['acquisition_cost']:,}".replace(",", " "),
            f"{row['residual_value']:,}".replace(",", " "), str(row["useful_life_months"]),
            str(row["depreciation_months"]),
            f"{row['accumulated_depreciation']:,}".replace(",", " "),
            f"{row['net_book_value']:,}".replace(",", " "),
        ])
    if len(table_rows) == 1:
        table_rows.append(["Aucune immobilisation", "—", "—", "0", "0", "—", "0", "0", "0"])
    table = Table(table_rows, repeatRows=1, colWidths=[48*mm, 30*mm, 22*mm, 25*mm, 22*mm, 15*mm, 14*mm, 28*mm, 25*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#174A6E")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D8E2E9")),
        ("FONTSIZE", (0,0), (-1,-1), 7), ("PADDING", (0,0), (-1,-1), 4),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (3,1), (-1,-1), "RIGHT"),
    ]))
    story.extend([table, Spacer(1, 4*mm), Paragraph(
        "Méthode linéaire indicative. La dotation mensuelle est calculée sur la base amortissable (coût moins valeur résiduelle). "
        "Les règles de prorata, de sortie d'actif et de conformité comptable/fiscale doivent être validées par un professionnel.",
        styles["Italic"])])
    doc.build(story)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
