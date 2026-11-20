from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token,hash_password,verify_password
from app.db import get_db
from app.dependencies import get_current_user,require_company_admin
from app.models import Company,Station,User
from app.schemas.tenant import OwnerRegistration,LoginInput,StationCreate,StationRead,CompanyRead,TokenRead
router=APIRouter()
@router.post("/auth/register-owner",response_model=TokenRead,status_code=201)
def register_owner(payload:OwnerRegistration,db:Session=Depends(get_db)):
    if settings.app_env=="production" and settings.bootstrap_secret.startswith("CHANGE_ME"):
        raise HTTPException(503,"Configuration initiale non sécurisée")
    if payload.bootstrap_secret!=settings.bootstrap_secret: raise HTTPException(403,"Code d'initialisation incorrect")
    email=payload.owner_email.strip().lower()
    if db.query(User).filter(User.email==email).first(): raise HTTPException(409,"Adresse e-mail déjà utilisée")
    company=Company(legal_name=payload.company_legal_name,display_name=payload.company_display_name,
      email=payload.company_email,phone=payload.company_phone,currency="XOF")
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
    user=db.query(User).filter(User.email==payload.email.strip().lower()).first()
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
    return db.query(Station).filter(Station.company_id==user.company_id,Station.is_active.is_(True)).order_by(Station.name).all()
@router.post("/stations",response_model=StationRead,status_code=201)
def create_station(payload:StationCreate,user:User=Depends(require_company_admin),db:Session=Depends(get_db)):
    station=Station(company_id=user.company_id,name=payload.name,code=payload.code.upper(),address=payload.address,city=payload.city)
    db.add(station)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Ce code de station existe déjà dans votre entreprise")
    db.refresh(station); return station
