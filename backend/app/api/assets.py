from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import FixedAsset, Station, User
router=APIRouter()
ROLES={"company_admin","station_manager"}
class AssetCreate(BaseModel):
 station_id:int=Field(gt=0)
 asset_code:str=Field(min_length=1,max_length=50)
 name:str=Field(min_length=2,max_length=180)
 category:str=Field(min_length=2,max_length=60)
 description:str|None=Field(default=None,max_length=500)
 supplier:str|None=Field(default=None,max_length=160)
 acquisition_date:date
 in_service_date:date
 acquisition_cost:int=Field(gt=0,le=2_000_000_000)
 residual_value:int=Field(default=0,ge=0,le=2_000_000_000)
 useful_life_months:int=Field(gt=0,le=1200)
 depreciation_method:Literal["straight_line"]="straight_line"
 @model_validator(mode="after")
 def validate_values(self):
  if self.residual_value>self.acquisition_cost: raise ValueError("La valeur résiduelle dépasse le coût")
  if self.in_service_date<self.acquisition_date: raise ValueError("La mise en service précède l'acquisition")
  return self
def _station(user,station_id,db):
 q=db.query(Station).filter(Station.id==station_id,Station.company_id==user.company_id,Station.is_active.is_(True))
 if user.station_id is not None:q=q.filter(Station.id==user.station_id)
 if not q.first():raise HTTPException(404,"Station introuvable ou non autorisée")
def _value(a,cutoff):
 base=a.acquisition_cost-a.residual_value
 months=0 if cutoff<a.in_service_date else (cutoff.year-a.in_service_date.year)*12+cutoff.month-a.in_service_date.month+1
 months=min(max(months,0),a.useful_life_months)
 accumulated=round(base*months/a.useful_life_months)
 return {"depreciation_months":months,"monthly_depreciation":round(base/a.useful_life_months),
 "accumulated_depreciation":accumulated,"net_book_value":a.acquisition_cost-accumulated,
 "depreciable_base":base,"fully_depreciated":months>=a.useful_life_months}
def _serialize(a,cutoff):
 return {"id":a.id,"company_id":a.company_id,"station_id":a.station_id,"asset_code":a.asset_code,
 "name":a.name,"category":a.category,"description":a.description,"supplier":a.supplier,
 "acquisition_date":a.acquisition_date,"in_service_date":a.in_service_date,"acquisition_cost":a.acquisition_cost,
 "residual_value":a.residual_value,"useful_life_months":a.useful_life_months,
 "depreciation_method":a.depreciation_method,"status":a.status,"as_of":cutoff,**_value(a,cutoff)}
@router.get("/assets")
def list_assets(station_id:int|None=None,as_of:date|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=db.query(FixedAsset).filter(FixedAsset.company_id==user.company_id)
 if user.station_id is not None:q=q.filter(FixedAsset.station_id==user.station_id)
 elif station_id is not None:q=q.filter(FixedAsset.station_id==station_id)
 cutoff=as_of or date.today()
 return [_serialize(a,cutoff) for a in q.order_by(FixedAsset.acquisition_date.desc()).limit(500).all()]
@router.post("/assets",status_code=201)
def create_asset(payload:AssetCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if user.role not in ROLES:raise HTTPException(403,"Droits de gestion des immobilisations requis")
 _station(user,payload.station_id,db)
 if db.query(FixedAsset).filter(FixedAsset.company_id==user.company_id,FixedAsset.asset_code==payload.asset_code.strip()).first():
  raise HTTPException(409,"Ce code immobilisation existe déjà")
 a=FixedAsset(company_id=user.company_id,station_id=payload.station_id,created_by=user.id,asset_code=payload.asset_code.strip(),
 name=payload.name.strip(),category=payload.category.strip(),description=payload.description,supplier=payload.supplier,
 acquisition_date=payload.acquisition_date,in_service_date=payload.in_service_date,acquisition_cost=payload.acquisition_cost,
 residual_value=payload.residual_value,useful_life_months=payload.useful_life_months,depreciation_method=payload.depreciation_method)
 db.add(a);db.commit();db.refresh(a)
 return _serialize(a,date.today())
@router.get("/assets/summary")
def assets_summary(station_id:int|None=None,as_of:date|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 q=db.query(FixedAsset).filter(FixedAsset.company_id==user.company_id)
 if user.station_id is not None:q=q.filter(FixedAsset.station_id==user.station_id)
 elif station_id is not None:q=q.filter(FixedAsset.station_id==station_id)
 cutoff=as_of or date.today(); rows=q.all(); vals=[_value(a,cutoff) for a in rows]
 return {"assets_count":len(rows),"acquisition_cost_total":sum(a.acquisition_cost for a in rows),
 "depreciable_base_total":sum(v["depreciable_base"] for v in vals),
 "monthly_depreciation_total":sum(v["monthly_depreciation"] for v in vals if not v["fully_depreciated"]),
 "accumulated_depreciation_total":sum(v["accumulated_depreciation"] for v in vals),
 "net_book_value_total":sum(v["net_book_value"] for v in vals),"as_of":cutoff,"method":"straight_line"}
