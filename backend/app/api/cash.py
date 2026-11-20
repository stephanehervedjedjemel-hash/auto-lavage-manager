from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.dependencies import get_current_user
from app.models import CashSession, CashMovement, Payment, TicketRefund, Station, User

router=APIRouter()

class OpenCash(BaseModel):
    station_id:int=Field(gt=0)
    opening_amount:int=Field(ge=0,le=2_000_000_000)
class MovementCreate(BaseModel):
    direction:str
    amount:int=Field(gt=0,le=2_000_000_000)
    reason:str=Field(min_length=3,max_length=180)
class CloseCash(BaseModel):
    closing_amount:int=Field(ge=0,le=2_000_000_000)

def visible_station(station_id:int,user:User,db:Session):
    q=db.query(Station).filter(Station.id==station_id,Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None: q=q.filter(Station.id==user.station_id)
    station=q.first()
    if not station: raise HTTPException(404,"Station introuvable ou non autorisée")
    return station

def cash_totals(session:CashSession,db:Session):
    cash_payments=db.query(func.coalesce(func.sum(Payment.amount),0)).filter(
        Payment.company_id==session.company_id,Payment.station_id==session.station_id,
        Payment.method=="cash",Payment.created_at>=session.opened_at
    )
    if session.closed_at: cash_payments=cash_payments.filter(Payment.created_at<=session.closed_at)
    collected=int(cash_payments.scalar() or 0)
    cash_refunds=db.query(func.coalesce(func.sum(TicketRefund.amount),0)).filter(
        TicketRefund.company_id==session.company_id,TicketRefund.station_id==session.station_id,
        TicketRefund.method=="cash",TicketRefund.refunded_at>=session.opened_at
    )
    if session.closed_at: cash_refunds=cash_refunds.filter(TicketRefund.refunded_at<=session.closed_at)
    collected-=int(cash_refunds.scalar() or 0)
    q=db.query(CashMovement).filter(CashMovement.session_id==session.id)
    if session.closed_at: q=q.filter(CashMovement.created_at<=session.closed_at)
    movements=q.all()
    inflows=sum(x.amount for x in movements if x.direction=="in")
    outflows=sum(x.amount for x in movements if x.direction=="out")
    return {"cash_payments":collected,"other_inflows":inflows,"outflows":outflows,
            "expected_amount":session.opening_amount+collected+inflows-outflows}

def serialize(session:CashSession,db:Session):
    totals=cash_totals(session,db)
    return {"id":session.id,"company_id":session.company_id,"station_id":session.station_id,
      "opening_amount":session.opening_amount,"closing_amount":session.closing_amount,
      "expected_amount":session.expected_amount if session.expected_amount is not None else totals["expected_amount"],
      "difference":session.difference,"status":session.status,"opened_at":session.opened_at,
      "closed_at":session.closed_at,"cash_payments":totals["cash_payments"],
      "other_inflows":totals["other_inflows"],"outflows":totals["outflows"]}

@router.get("/cash/summary")
def cash_summary(station_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(CashSession).filter(CashSession.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(CashSession.station_id==user.station_id)
    elif station_id is not None: q=q.filter(CashSession.station_id==station_id)
    sessions=q.order_by(CashSession.opened_at.desc()).limit(30).all()
    payments=db.query(Payment).filter(Payment.company_id==user.company_id)
    if user.station_id is not None: payments=payments.filter(Payment.station_id==user.station_id)
    elif station_id is not None: payments=payments.filter(Payment.station_id==station_id)
    all_payments=payments.all()
    refunds=db.query(TicketRefund).filter(TicketRefund.company_id==user.company_id)
    if user.station_id is not None: refunds=refunds.filter(TicketRefund.station_id==user.station_id)
    elif station_id is not None: refunds=refunds.filter(TicketRefund.station_id==station_id)
    all_refunds=refunds.all()
    by_method={}
    for p in all_payments: by_method[p.method]=by_method.get(p.method,0)+p.amount
    for refund in all_refunds: by_method[refund.method]=by_method.get(refund.method,0)-refund.amount
    total_collected=sum(by_method.values())
    return {"total_collected":total_collected,"payments_count":len(all_payments),
      "by_method":by_method,"open_sessions":[serialize(s,db) for s in sessions if s.status=="open"],
      "recent_sessions":[serialize(s,db) for s in sessions]}

@router.get("/cash/sessions")
def list_sessions(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(CashSession).filter(CashSession.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(CashSession.station_id==user.station_id)
    return [serialize(s,db) for s in q.order_by(CashSession.opened_at.desc()).limit(100).all()]

@router.post("/cash/sessions",status_code=201)
def open_session(payload:OpenCash,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in {"company_admin","station_manager","cashier"}: raise HTTPException(403,"Droits de caisse requis")
    visible_station(payload.station_id,user,db)
    existing=db.query(CashSession).filter(CashSession.company_id==user.company_id,
      CashSession.station_id==payload.station_id,CashSession.status=="open").first()
    if existing: raise HTTPException(409,"Une session de caisse est déjà ouverte pour cette station")
    session=CashSession(company_id=user.company_id,station_id=payload.station_id,
      opened_by=user.id,opening_amount=payload.opening_amount,status="open")
    db.add(session);db.commit();db.refresh(session)
    return serialize(session,db)

@router.post("/cash/sessions/{session_id}/movements",status_code=201)
def add_movement(session_id:int,payload:MovementCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in {"company_admin","station_manager","cashier"}: raise HTTPException(403,"Droits de caisse requis")
    if payload.direction not in {"in","out"}: raise HTTPException(422,"Le sens doit être in ou out")
    q=db.query(CashSession).filter(CashSession.id==session_id,CashSession.company_id==user.company_id,CashSession.status=="open")
    if user.station_id is not None: q=q.filter(CashSession.station_id==user.station_id)
    session=q.first()
    if not session: raise HTTPException(404,"Session ouverte introuvable")
    movement=CashMovement(company_id=user.company_id,station_id=session.station_id,session_id=session.id,
      created_by=user.id,direction=payload.direction,amount=payload.amount,reason=payload.reason)
    db.add(movement);db.commit();db.refresh(movement)
    return {"id":movement.id,"direction":movement.direction,"amount":movement.amount,"reason":movement.reason,"created_at":movement.created_at}

@router.post("/cash/sessions/{session_id}/close")
def close_session(session_id:int,payload:CloseCash,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in {"company_admin","station_manager","cashier"}: raise HTTPException(403,"Droits de caisse requis")
    q=db.query(CashSession).filter(CashSession.id==session_id,CashSession.company_id==user.company_id,CashSession.status=="open")
    if user.station_id is not None: q=q.filter(CashSession.station_id==user.station_id)
    session=q.first()
    if not session: raise HTTPException(404,"Session ouverte introuvable")
    session.closed_at=datetime.now(timezone.utc)
    session.closed_by=user.id
    totals=cash_totals(session,db)
    session.expected_amount=totals["expected_amount"]
    session.closing_amount=payload.closing_amount
    session.difference=payload.closing_amount-session.expected_amount
    session.status="closed"
    db.commit();db.refresh(session)
    return serialize(session,db)
