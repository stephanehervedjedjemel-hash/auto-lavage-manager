from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token,hash_password,verify_password
from app.db import get_db
from app.dependencies import get_current_user,require_company_admin
from app.models import Company,Station,User
from app.schemas.tenant import (OwnerRegistration,LoginInput,StationCreate,StationRead,
    CompanyRead,TokenRead,UserCreate,UserRead,UserStatusUpdate)
router=APIRouter()
@router.post("/auth/register-owner",response_model=TokenRead,status_code=201)
def register_owner(payload:OwnerRegistration,db:Session=Depends(get_db)):
    if settings.app_env=="production" and settings.bootstrap_secret.startswith("CHANGE_ME"):
        raise HTTPException(503,"Configuration initiale non sécurisée")
    if payload.bootstrap_secret!=settings.bootstrap_secret: raise HTTPException(403,"Code d'initialisation incorrect")
    email=str(payload.owner_email).strip().lower()
    if db.query(User).filter(User.email==email).first(): raise HTTPException(409,"Adresse e-mail déjà utilisée")
    company=Company(legal_name=payload.company_legal_name,display_name=payload.company_display_name,
      email=str(payload.company_email).lower() if payload.company_email else None,phone=payload.company_phone,currency="XOF")
    company.stations.append(Station(name=payload.station_name,code=payload.station_code.upper(),
      address=payload.station_address,city=payload.station_city))
    user=User(full_name=payload.owner_full_name,email=email,password_hash=hash_password(payload.password),role="company_admin")
    company.users.append(user); db.add(company)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Entreprise ou station déjà enregistrée")
    db.refresh(user)
    return TokenRead(access_token=create_access_token(user_id=user.id,company_id=company.id,role=user.role),
      company_id=company.id,user_id=user.id,role=user.role)
@router.post("/auth/login",response_model=TokenRead)
def login(payload:LoginInput,db:Session=Depends(get_db)):
    user=db.query(User).filter(User.email==str(payload.email).lower()).first()
    if not user or not user.is_active or not verify_password(payload.password,user.password_hash):
        raise HTTPException(401,"E-mail ou mot de passe incorrect",headers={"WWW-Authenticate":"Bearer"})
    return TokenRead(access_token=create_access_token(user_id=user.id,company_id=user.company_id,role=user.role),
      company_id=user.company_id,user_id=user.id,role=user.role)
@router.get("/companies/me",response_model=CompanyRead)
def get_my_company(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    company=db.query(Company).filter(Company.id==user.company_id,Company.is_active.is_(True)).first()
    if company is None: raise HTTPException(404,"Entreprise introuvable")
    return company
@router.get("/stations",response_model=list[StationRead])
def list_stations(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    query=db.query(Station).filter(Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None: query=query.filter(Station.id==user.station_id)
    return query.order_by(Station.name).all()
@router.post("/stations",response_model=StationRead,status_code=201)
def create_station(payload:StationCreate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    station=Station(company_id=user.company_id,name=payload.name,code=payload.code.upper(),address=payload.address,city=payload.city)
    db.add(station)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Ce code de station existe déjà dans votre entreprise")
    db.refresh(station); return station
@router.get("/users",response_model=list[UserRead])
def list_users(user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    return db.query(User).filter(User.company_id==user.company_id).order_by(User.full_name).all()
@router.post("/users",response_model=UserRead,status_code=201)
def create_user(payload:UserCreate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    if payload.role not in {"company_admin","station_manager","operator","cashier"}:
        raise HTTPException(422,"Rôle non autorisé")
    email=str(payload.email).strip().lower()
    if db.query(User).filter(User.email==email).first(): raise HTTPException(409,"Cette adresse e-mail est déjà utilisée")
    if payload.station_id is not None:
        station=db.query(Station).filter(Station.id==payload.station_id,Station.company_id==user.company_id,Station.is_active.is_(True)).first()
        if station is None: raise HTTPException(404,"Station introuvable dans votre entreprise")
    new_user=User(company_id=user.company_id,station_id=payload.station_id,full_name=payload.full_name,
      email=email,password_hash=hash_password(payload.password),role=payload.role)
    db.add(new_user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Impossible de créer ce compte")
    db.refresh(new_user); return new_user
@router.patch("/users/{user_id}/status",response_model=UserRead)
def update_user_status(user_id:int,payload:UserStatusUpdate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    target=db.query(User).filter(User.id==user_id,User.company_id==user.company_id).first()
    if target is None: raise HTTPException(404,"Utilisateur introuvable")
    if target.id==user.id and not payload.is_active: raise HTTPException(400,"Vous ne pouvez pas désactiver votre propre compte")
    target.is_active=payload.is_active
    db.commit(); db.refresh(target); return target
