from datetime import datetime,timezone
from secrets import token_hex
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import CommissionEntry,CommissionPayment,Employee,Payment,Service,Station,Ticket,TicketLine,TicketRefund,User
from app.commissioning import accrue_commission
from app.schemas.ticket import TicketCreate,TicketRead,PaymentCreate,PaymentRead
router=APIRouter()
def _ticket_read(ticket:Ticket,db:Session):
    payments=db.query(Payment).filter(Payment.ticket_id==ticket.id).order_by(Payment.id).all()
    paid=sum(p.amount for p in payments)
    lines=db.query(TicketLine).filter(TicketLine.ticket_id==ticket.id).order_by(TicketLine.id).all()
    return {"id":ticket.id,"company_id":ticket.company_id,"station_id":ticket.station_id,
        "ticket_number":ticket.ticket_number,"customer_name":ticket.customer_name,"customer_phone":ticket.customer_phone,
        "vehicle_type":ticket.vehicle_type,"vehicle_registration":ticket.vehicle_registration,
        "subtotal":ticket.subtotal,"discount":ticket.discount,"total":ticket.total,"paid_amount":paid,
        "remaining_amount":ticket.total-paid,"status":ticket.status,"created_at":ticket.created_at,
        "lines":[{"id":x.id,"service_id":x.service_id,"service_code":x.service_code,"service_name":x.service_name,"quantity":x.quantity,"unit_price":x.unit_price,"line_total":x.line_total,"employee_id":x.employee_id} for x in lines],"payments":payments,"refunds":db.query(TicketRefund).filter(TicketRefund.ticket_id==ticket.id).order_by(TicketRefund.id).all(),"refunded_amount":db.query(func.coalesce(func.sum(TicketRefund.amount),0)).filter(TicketRefund.ticket_id==ticket.id).scalar() or 0}
def _visible_ticket(ticket_id:int,user:User,db:Session):
    q=db.query(Ticket).filter(Ticket.id==ticket_id,Ticket.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Ticket.station_id==user.station_id)
    ticket=q.first()
    if ticket is None: raise HTTPException(404,"Ticket introuvable")
    return ticket
@router.post("/tickets",response_model=TicketRead,status_code=201)
def create_ticket(payload:TicketCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    station=db.query(Station).filter(Station.id==payload.station_id,Station.company_id==user.company_id,Station.is_active.is_(True)).first()
    if station is None: raise HTTPException(404,"Station introuvable dans votre entreprise")
    if user.station_id is not None and user.station_id!=station.id: raise HTTPException(403,"Vous ne pouvez créer un ticket que dans votre station")
    if user.role not in {"company_admin","station_manager","operator","cashier"}: raise HTTPException(403,"Droits insuffisants")
    service_ids=[line.service_id for line in payload.lines]
    if len(set(service_ids))!=len(service_ids): raise HTTPException(422,"Regroupez les quantités d'une même prestation sur une ligne")
    services=db.query(Service).filter(Service.id.in_(service_ids),Service.company_id==user.company_id,Service.is_active.is_(True)).all()
    by_id={s.id:s for s in services}
    if len(by_id)!=len(service_ids): raise HTTPException(422,"Une prestation est inconnue ou inactive")
    lines=[]; subtotal=0
    for line in payload.lines:
        service=by_id[line.service_id]
        employee=None
        if line.employee_id is not None:
            employee=db.query(Employee).filter(Employee.id==line.employee_id,Employee.company_id==user.company_id,
                Employee.station_id==station.id,Employee.is_active.is_(True)).first()
            if employee is None: raise HTTPException(422,"Le laveur est absent, inactif ou rattaché à une autre station")
        if service.station_id is not None and service.station_id!=station.id:
            raise HTTPException(422,f"La prestation {service.name} n'est pas disponible dans cette station")
        total=service.price*line.quantity; subtotal+=total
        lines.append(TicketLine(service_id=service.id,service_code=service.code,service_name=service.name,
            quantity=line.quantity,unit_price=service.price,line_total=total,employee_id=employee.id if employee else None))
    now=datetime.now(timezone.utc)
    ticket=Ticket(company_id=user.company_id,station_id=station.id,
        ticket_number=f"ALM-{now:%Y%m%d}-{token_hex(4).upper()}",
        customer_name=payload.customer_name,customer_phone=payload.customer_phone,
        vehicle_type=payload.vehicle_type,vehicle_registration=payload.vehicle_registration,
        subtotal=subtotal,discount=0,total=subtotal,status="unpaid",created_by=user.id)
    db.add(ticket); db.flush()
    for line in lines: line.ticket_id=ticket.id; db.add(line)
    db.flush()
    for line in lines:
        if line.employee_id is not None:
            accrue_commission(db,ticket,line,employee_id=line.employee_id)
    db.commit(); db.refresh(ticket)
    return _ticket_read(ticket,db)
@router.get("/tickets",response_model=list[TicketRead])
def list_tickets(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Ticket).filter(Ticket.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Ticket.station_id==user.station_id)
    tickets=q.order_by(Ticket.created_at.desc(),Ticket.id.desc()).limit(100).all()
    return [_ticket_read(t,db) for t in tickets]
@router.get("/tickets/{ticket_id}",response_model=TicketRead)
def get_ticket(ticket_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return _ticket_read(_visible_ticket(ticket_id,user,db),db)
@router.post("/tickets/{ticket_id}/payments",response_model=PaymentRead,status_code=201)
def add_payment(ticket_id:int,payload:PaymentCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    ticket=_visible_ticket(ticket_id,user,db)
    if ticket.status=="cancelled": raise HTTPException(409,"Un ticket annulé ne peut pas être encaissé")
    if user.role not in {"company_admin","station_manager","cashier"}: raise HTTPException(403,"Droits de caisse requis")
    paid=sum(p.amount for p in db.query(Payment).filter(Payment.ticket_id==ticket.id).all())
    remaining=ticket.total-paid
    if payload.amount>remaining: raise HTTPException(422,f"Le paiement dépasse le solde restant ({remaining})")
    payment=Payment(ticket_id=ticket.id,company_id=user.company_id,station_id=ticket.station_id,
        amount=payload.amount,method=payload.method,reference=payload.reference,received_by=user.id)
    db.add(payment)
    ticket.status="paid" if payload.amount==remaining else "partial"
    db.commit(); db.refresh(payment)
    return payment


class TicketCancellation(BaseModel):
    reason: str = Field(min_length=5, max_length=250)


@router.post("/tickets/{ticket_id}/cancel", response_model=TicketRead)
def cancel_ticket(ticket_id: int, payload: TicketCancellation,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in {"company_admin", "station_manager"}:
        raise HTTPException(403, "Seuls les responsables peuvent annuler un ticket")
    ticket = _visible_ticket(ticket_id, user, db)
    if ticket.status == "cancelled":
        raise HTTPException(409, "Ce ticket est déjà annulé")

    entries = db.query(CommissionEntry).filter(
        CommissionEntry.ticket_id == ticket.id,
        CommissionEntry.company_id == user.company_id,
    ).with_for_update().all()
    for entry in entries:
        paid = db.query(func.coalesce(func.sum(CommissionPayment.amount), 0)).filter(
            CommissionPayment.commission_entry_id == entry.id
        ).scalar() or 0
        if paid:
            raise HTTPException(409, "Une commission a déjà été réglée. Effectuez d'abord une régularisation de commission.")

    payments = db.query(Payment).filter(
        Payment.ticket_id == ticket.id, Payment.company_id == user.company_id,
        Payment.station_id == ticket.station_id,
    ).order_by(Payment.id).all()
    for payment in payments:
        db.add(TicketRefund(
            ticket_id=ticket.id, payment_id=payment.id, company_id=user.company_id,
            station_id=ticket.station_id, amount=payment.amount, method=payment.method,
            reference=payment.reference, reason=payload.reason.strip(), refunded_by=user.id,
        ))
    for entry in entries:
        entry.status = "cancelled"
    ticket.status = "cancelled"
    db.commit()
    db.refresh(ticket)
    return _ticket_read(ticket, db)
