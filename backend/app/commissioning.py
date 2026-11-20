from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.models import CommissionEntry, CommissionRule, Employee, Ticket, TicketLine

def accrue_commission(db: Session, ticket: Ticket, line: TicketLine, employee_id: int) -> CommissionEntry | None:
    """Snapshot the applicable commission at ticket creation; later rule edits cannot rewrite it."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id == ticket.company_id,
        Employee.station_id == ticket.station_id,
        Employee.is_active.is_(True),
    ).first()
    if employee is None:
        return None
    work_date = (ticket.created_at or datetime.now(timezone.utc)).date()
    rules = db.query(CommissionRule).filter(
        CommissionRule.company_id == ticket.company_id,
        CommissionRule.is_active.is_(True),
        CommissionRule.effective_from <= work_date,
        (CommissionRule.effective_to.is_(None) | (CommissionRule.effective_to >= work_date)),
        ((CommissionRule.station_id.is_(None)) | (CommissionRule.station_id == ticket.station_id)),
        ((CommissionRule.employee_id.is_(None)) | (CommissionRule.employee_id == employee_id)),
        ((CommissionRule.service_id.is_(None)) | (CommissionRule.service_id == line.service_id)),
    ).order_by(CommissionRule.effective_from.desc(), CommissionRule.id.desc()).all()
    if not rules:
        return None
    # Employee + service rules outrank employee-only/service-only; those outrank global rules.
    rule = max(rules, key=lambda r: (int(r.employee_id is not None) + int(r.service_id is not None),
                                    int(r.station_id is not None), r.effective_from, r.id))
    if rule.calculation_type == "fixed":
        amount = rule.value * line.quantity
    else:
        amount = int((Decimal(line.line_total) * Decimal(rule.value) / Decimal(10000))
                     .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    entry = CommissionEntry(
        company_id=ticket.company_id, station_id=ticket.station_id,
        ticket_id=ticket.id, ticket_line_id=line.id, employee_id=employee.id,
        rule_id=rule.id, employee_name=employee.full_name, service_name=line.service_name,
        basis_amount=line.line_total, calculation_type=rule.calculation_type,
        rule_value=rule.value, amount=amount, status="earned",
    )
    db.add(entry)
    return entry
