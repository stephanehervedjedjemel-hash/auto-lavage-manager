from datetime import datetime,timezone
from secrets import token_hex
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Payment,Service,Station,Ticket,TicketLine,User
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
        "lines":lines,"payments":payments}
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
        if service.station_id is not None and service.station_id!=station.id:
            raise HTTPException(422,f"La prestation {service.name} n'est pas disponible dans cette station")
        total=service.price*line.quantity; subtotal+=total
        lines.append(TicketLine(service_id=service.id,service_code=service.code,service_name=service.name,
            quantity=line.quantity,unit_price=service.price,line_total=total))
    now=datetime.now(timezone.utc)
    ticket=Ticket(company_id=user.company_id,station_id=station.id,
        ticket_number=f"ALM-{now:%Y%m%d}-{token_hex(4).upper()}",
        customer_name=payload.customer_name,customer_phone=payload.customer_phone,
        vehicle_type=payload.vehicle_type,vehicle_registration=payload.vehicle_registration,
        subtotal=subtotal,discount=0,total=subtotal,status="unpaid",created_by=user.id)
    db.add(ticket); db.flush()
    for line in lines: line.ticket_id=ticket.id; db.add(line)
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
