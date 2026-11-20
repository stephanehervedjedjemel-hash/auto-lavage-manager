from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user, require_company_admin
from app.models import Service, Station, User
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
router=APIRouter()
@router.get("/services",response_model=list[ServiceRead])
def list_services(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    query=db.query(Service).filter(Service.company_id==user.company_id,Service.is_active.is_(True))
    if user.station_id is not None:
        query=query.filter((Service.station_id.is_(None))|(Service.station_id==user.station_id))
    return query.order_by(Service.category,Service.name).all()
@router.post("/services",response_model=ServiceRead,status_code=201)
def create_service(payload:ServiceCreate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    if payload.station_id is not None:
        station=db.query(Station).filter(Station.id==payload.station_id,Station.company_id==user.company_id,Station.is_active.is_(True)).first()
        if station is None: raise HTTPException(404,"Station introuvable dans votre entreprise")
    item=Service(company_id=user.company_id,station_id=payload.station_id,code=payload.code.upper(),
        name=payload.name,description=payload.description,category=payload.category,
        price=payload.price,duration_minutes=payload.duration_minutes)
    db.add(item)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Un service portant ce code existe déjà pour ce périmètre")
    db.refresh(item); return item
@router.patch("/services/{service_id}",response_model=ServiceRead)
def update_service(service_id:int,payload:ServiceUpdate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    item=db.query(Service).filter(Service.id==service_id,Service.company_id==user.company_id).first()
    if item is None: raise HTTPException(404,"Prestation introuvable")
    for key,value in payload.model_dump(exclude_unset=True).items():
        setattr(item,key,value)
    db.commit(); db.refresh(item); return item
