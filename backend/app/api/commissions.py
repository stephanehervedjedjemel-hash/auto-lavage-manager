from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import CommissionEntry, CommissionPayment, CommissionRule, Employee, Service, Station, User

router = APIRouter()
MANAGERS = {"company_admin", "station_manager"}
PAYMENT_METHODS = {"cash", "wave", "orange_money", "mtn_money", "moov_money", "card", "bank_transfer", "other"}

class CommissionRuleCreate(BaseModel):
    station_id: int | None = Field(default=None, gt=0)
    employee_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    calculation_type: Literal["fixed", "percent"]
    # fixed = FCFA per service unit; percent = basis points (100 = 1%, 1000 = 10%).
    value: int = Field(gt=0, le=100_000_000)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("La fin d'application précède le début")
        if self.calculation_type == "percent" and self.value > 10000:
            raise ValueError("Le taux ne peut pas dépasser 100 %")
        return self

class CommissionPaymentCreate(BaseModel):
    amount: int = Field(gt=0, le=2_000_000_000)
    method: Literal["cash", "wave", "orange_money", "mtn_money", "moov_money", "card", "bank_transfer", "other"]
    reference: str | None = Field(default=None, max_length=100)

def _station_scope(user: User, station_id: int | None, db: Session):
    if station_id is None:
        return
    q = db.query(Station).filter(Station.id == station_id, Station.company_id == user.company_id, Station.is_active.is_(True))
    if user.station_id is not None:
        q = q.filter(Station.id == user.station_id)
    if q.first() is None:
        raise HTTPException(404, "Station introuvable ou non autorisée")

def _entry_data(entry: CommissionEntry, db: Session):
    paid = int(db.query(func.coalesce(func.sum(CommissionPayment.amount), 0))
               .filter(CommissionPayment.commission_entry_id == entry.id).scalar() or 0)
    return {
        "id": entry.id, "ticket_id": entry.ticket_id, "ticket_line_id": entry.ticket_line_id,
        "station_id": entry.station_id, "employee_id": entry.employee_id,
        "employee_name": entry.employee_name, "service_name": entry.service_name,
        "basis_amount": entry.basis_amount, "calculation_type": entry.calculation_type,
        "rule_value": entry.rule_value, "amount": entry.amount, "paid_amount": paid,
        "remaining_amount": entry.amount - paid, "status": "paid" if paid == entry.amount else ("partial" if paid else "earned"),
        "earned_at": entry.earned_at,
    }

@router.post("/commission-rules", status_code=201)
def create_commission_rule(payload: CommissionRuleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Droits de paramétrage des commissions requis")
    _station_scope(user, payload.station_id, db)
    if payload.employee_id is not None:
        q = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.company_id == user.company_id)
        if payload.station_id is not None:
            q = q.filter(Employee.station_id == payload.station_id)
        elif user.station_id is not None:
            q = q.filter(Employee.station_id == user.station_id)
        if q.first() is None:
            raise HTTPException(404, "Laveur introuvable ou non autorisé")
    if payload.service_id is not None:
        q = db.query(Service).filter(Service.id == payload.service_id, Service.company_id == user.company_id)
        if payload.station_id is not None:
            q = q.filter((Service.station_id.is_(None)) | (Service.station_id == payload.station_id))
        if q.first() is None:
            raise HTTPException(404, "Prestation introuvable ou non autorisée")
    rule = CommissionRule(company_id=user.company_id, created_by=user.id,
        station_id=payload.station_id or user.station_id, employee_id=payload.employee_id,
        service_id=payload.service_id, code=payload.code.strip().upper(), name=payload.name.strip(),
        calculation_type=payload.calculation_type, value=payload.value,
        effective_from=payload.effective_from, effective_to=payload.effective_to)
    db.add(rule)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        if "uq_commission_rule_company_code" in str(exc):
            raise HTTPException(409, "Ce code de commission existe déjà") from exc
        raise
    db.refresh(rule)
    return {"id": rule.id, "code": rule.code, "name": rule.name, "station_id": rule.station_id,
            "employee_id": rule.employee_id, "service_id": rule.service_id,
            "calculation_type": rule.calculation_type, "value": rule.value,
            "effective_from": rule.effective_from, "effective_to": rule.effective_to}

@router.get("/commission-rules")
def list_commission_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Droits de consultation des barèmes requis")
    q = db.query(CommissionRule).filter(CommissionRule.company_id == user.company_id)
    if user.station_id is not None:
        q = q.filter((CommissionRule.station_id.is_(None)) | (CommissionRule.station_id == user.station_id))
    return [{"id": r.id, "code": r.code, "name": r.name, "station_id": r.station_id,
             "employee_id": r.employee_id, "service_id": r.service_id, "calculation_type": r.calculation_type,
             "value": r.value, "effective_from": r.effective_from, "effective_to": r.effective_to,
             "is_active": r.is_active} for r in q.order_by(CommissionRule.effective_from.desc()).limit(500).all()]

@router.get("/commissions")
def list_commissions(start_date: date | None = None, end_date: date | None = None,
                     station_id: int | None = None, employee_id: int | None = None,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Droits de consultation des commissions requis")
    q = db.query(CommissionEntry).filter(CommissionEntry.company_id == user.company_id)
    if user.station_id is not None:
        q = q.filter(CommissionEntry.station_id == user.station_id)
    elif station_id is not None:
        q = q.filter(CommissionEntry.station_id == station_id)
    if employee_id is not None:
        q = q.filter(CommissionEntry.employee_id == employee_id)
    if start_date is not None:
        q = q.filter(func.date(CommissionEntry.earned_at) >= start_date)
    if end_date is not None:
        q = q.filter(func.date(CommissionEntry.earned_at) <= end_date)
    rows = q.order_by(CommissionEntry.earned_at.desc(), CommissionEntry.id.desc()).limit(2000).all()
    items = [_entry_data(row, db) for row in rows]
    return {"count": len(items), "earned_total": sum(x["amount"] for x in items),
            "paid_total": sum(x["paid_amount"] for x in items),
            "remaining_total": sum(x["remaining_amount"] for x in items), "items": items}

@router.post("/commissions/{entry_id}/payments", status_code=201)
def pay_commission(entry_id: int, payload: CommissionPaymentCreate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Droits de règlement des commissions requis")
    q = db.query(CommissionEntry).filter(CommissionEntry.id == entry_id,
        CommissionEntry.company_id == user.company_id)
    if user.station_id is not None:
        q = q.filter(CommissionEntry.station_id == user.station_id)
    entry = q.with_for_update().first()
    if entry is None:
        raise HTTPException(404, "Commission introuvable")
    paid = int(db.query(func.coalesce(func.sum(CommissionPayment.amount), 0))
               .filter(CommissionPayment.commission_entry_id == entry.id).scalar() or 0)
    if payload.amount > entry.amount - paid:
        raise HTTPException(422, "Le règlement dépasse le solde de commission")
    payment = CommissionPayment(commission_entry_id=entry.id, company_id=user.company_id,
        station_id=entry.station_id, paid_by=user.id, amount=payload.amount,
        method=payload.method, reference=payload.reference)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"id": payment.id, "commission_entry_id": entry.id, "amount": payment.amount,
            "method": payment.method, "reference": payment.reference, "paid_at": payment.paid_at}
