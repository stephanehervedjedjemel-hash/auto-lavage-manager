from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Supplier,InventoryProduct,SupplierProductPrice,StockMovement,Station,User
router=APIRouter()
MANAGERS={"company_admin","station_manager"}
class SupplierInput(BaseModel):
    name:str=Field(min_length=2,max_length=180)
    phone:str|None=Field(default=None,max_length=40)
    email:str|None=Field(default=None,max_length=255)
    address:str|None=Field(default=None,max_length=255)
class ProductInput(BaseModel):
    sku:str=Field(min_length=1,max_length=60)
    name:str=Field(min_length=2,max_length=180)
    category:str=Field(min_length=2,max_length=60)
    unit:str=Field(default="unite",min_length=1,max_length=20)
    minimum_stock:int=Field(default=0,ge=0,le=2000000000)
class PriceInput(BaseModel):
    purchase_price:int=Field(ge=0,le=2000000000)
class MovementInput(BaseModel):
    station_id:int=Field(gt=0)
    product_id:int=Field(gt=0)
    movement_type:Literal["in","out","adjustment"]
    quantity:int=Field(gt=0,le=2000000000)
    supplier_id:int|None=None
    unit_cost:int=Field(default=0,ge=0,le=2000000000)
    reference:str|None=Field(default=None,max_length=100)
    note:str|None=Field(default=None,max_length=500)
def _station(user,station_id,db):
    q=db.query(Station).filter(Station.id==station_id,Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None:q=q.filter(Station.id==user.station_id)
    if not q.first():raise HTTPException(404,"Station introuvable ou non autorisée")
def _stock(product_id,station_id,company_id,db):
    rows=db.query(StockMovement).filter(StockMovement.product_id==product_id,
      StockMovement.station_id==station_id,StockMovement.company_id==company_id).all()
    return sum(x.quantity if x.movement_type in ("in","adjustment") else -x.quantity for x in rows)
def _product(row,user,db):
    stocks=db.query(Station).filter(Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None:stocks=stocks.filter(Station.id==user.station_id)
    stock_by_station=[{"station_id":s.id,"station_name":s.name,"quantity":_stock(row.id,s.id,user.company_id,db)} for s in stocks.all()]
    prices=db.query(SupplierProductPrice,Supplier).join(Supplier,Supplier.id==SupplierProductPrice.supplier_id).filter(
      SupplierProductPrice.product_id==row.id,SupplierProductPrice.company_id==user.company_id).all()
    total=sum(x["quantity"] for x in stock_by_station)
    return {"id":row.id,"sku":row.sku,"name":row.name,"category":row.category,"unit":row.unit,
      "minimum_stock":row.minimum_stock,"is_active":row.is_active,"stock_total":total,
      "low_stock":total<=row.minimum_stock,"stock_by_station":stock_by_station,
      "supplier_prices":[{"supplier_id":p.supplier_id,"supplier_name":s.name,"purchase_price":p.purchase_price,"updated_at":p.updated_at} for p,s in prices]}
@router.get("/suppliers")
def suppliers(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [{"id":x.id,"name":x.name,"phone":x.phone,"email":x.email,"address":x.address,"is_active":x.is_active}
      for x in db.query(Supplier).filter(Supplier.company_id==user.company_id).order_by(Supplier.name).all()]
@router.post("/suppliers",status_code=201)
def create_supplier(p:SupplierInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Gestion des fournisseurs réservée aux responsables")
    row=Supplier(company_id=user.company_id,name=p.name.strip(),phone=p.phone,email=p.email,address=p.address)
    db.add(row)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,"Ce fournisseur existe déjà")
    db.refresh(row);return {"id":row.id,"name":row.name}
@router.get("/inventory/products")
def products(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [_product(x,user,db) for x in db.query(InventoryProduct).filter(
      InventoryProduct.company_id==user.company_id).order_by(InventoryProduct.name).all()]
@router.post("/inventory/products",status_code=201)
def create_product(p:ProductInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Création de produits réservée aux responsables")
    row=InventoryProduct(company_id=user.company_id,sku=p.sku.strip(),name=p.name.strip(),
      category=p.category.strip(),unit=p.unit,minimum_stock=p.minimum_stock)
    db.add(row)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,"Ce code produit existe déjà")
    db.refresh(row);return _product(row,user,db)
@router.put("/inventory/products/{product_id}/suppliers/{supplier_id}/price")
def set_supplier_price(product_id:int,supplier_id:int,p:PriceInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Modification des prix réservée aux responsables")
    product=db.query(InventoryProduct).filter(InventoryProduct.id==product_id,InventoryProduct.company_id==user.company_id).first()
    supplier=db.query(Supplier).filter(Supplier.id==supplier_id,Supplier.company_id==user.company_id,Supplier.is_active.is_(True)).first()
    if not product or not supplier:raise HTTPException(404,"Produit ou fournisseur introuvable")
    row=db.query(SupplierProductPrice).filter(SupplierProductPrice.product_id==product_id,SupplierProductPrice.supplier_id==supplier_id).first()
    if row:row.purchase_price=p.purchase_price
    else:row=SupplierProductPrice(company_id=user.company_id,product_id=product_id,supplier_id=supplier_id,purchase_price=p.purchase_price);db.add(row)
    db.commit();db.refresh(row);return {"product_id":product_id,"supplier_id":supplier_id,"purchase_price":row.purchase_price}
@router.get("/inventory/movements")
def movements(station_id:int|None=None,product_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(StockMovement).filter(StockMovement.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(StockMovement.station_id==user.station_id)
    elif station_id is not None:_station(user,station_id,db);q=q.filter(StockMovement.station_id==station_id)
    if product_id:q=q.filter(StockMovement.product_id==product_id)
    return [{"id":x.id,"station_id":x.station_id,"product_id":x.product_id,"supplier_id":x.supplier_id,
      "movement_type":x.movement_type,"quantity":x.quantity,"unit_cost":x.unit_cost,
      "reference":x.reference,"note":x.note,"moved_at":x.moved_at} for x in q.order_by(StockMovement.moved_at.desc()).limit(500).all()]
@router.post("/inventory/movements",status_code=201)
def create_movement(p:MovementInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Mouvements de stock réservés aux responsables")
    _station(user,p.station_id,db)
    product=db.query(InventoryProduct).filter(InventoryProduct.id==p.product_id,
      InventoryProduct.company_id==user.company_id,InventoryProduct.is_active.is_(True)).first()
    if not product:raise HTTPException(404,"Produit introuvable")
    if p.supplier_id is not None:
      supplier=db.query(Supplier).filter(Supplier.id==p.supplier_id,Supplier.company_id==user.company_id,Supplier.is_active.is_(True)).first()
      if not supplier:raise HTTPException(404,"Fournisseur introuvable")
      if p.movement_type!="in":raise HTTPException(422,"Un fournisseur ne peut être associé qu'à une entrée")
      price=db.query(SupplierProductPrice).filter(SupplierProductPrice.product_id==p.product_id,
        SupplierProductPrice.supplier_id==p.supplier_id).first()
      if price and p.unit_cost!=price.purchase_price:
        pass
      elif not price:
        db.add(SupplierProductPrice(company_id=user.company_id,supplier_id=p.supplier_id,
          product_id=p.product_id,purchase_price=p.unit_cost))
    if p.movement_type=="out" and p.quantity>_stock(p.product_id,p.station_id,user.company_id,db):
      raise HTTPException(422,"Stock insuffisant pour cette sortie")
    row=StockMovement(company_id=user.company_id,station_id=p.station_id,product_id=p.product_id,
      supplier_id=p.supplier_id,created_by=user.id,movement_type=p.movement_type,
      quantity=p.quantity,unit_cost=p.unit_cost,reference=p.reference,note=p.note)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"movement_type":row.movement_type,"quantity":row.quantity,
      "stock_after":_stock(p.product_id,p.station_id,user.company_id,db)}
@router.get("/inventory/summary")
def summary(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    items=[_product(x,user,db) for x in db.query(InventoryProduct).filter(InventoryProduct.company_id==user.company_id,InventoryProduct.is_active.is_(True)).all()]
    return {"products_count":len(items),"low_stock_count":sum(x["low_stock"] for x in items),
      "stock_units":sum(x["stock_total"] for x in items),"low_stock_products":[x for x in items if x["low_stock"]]}
