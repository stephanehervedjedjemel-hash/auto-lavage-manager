from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Expense, ExpensePayment, Station, User

router=APIRouter()
ALLOWED_ROLES={"company_admin","station_manager","cashier"}
CATEGORIES={"eau","electricite","produits_lavage","salaires","loyer","entretien","transport","administration","autres"}
METHODS={"cash","wave","orange_money","mtn_money","moov_money","card","bank_transfer","other"}

class ExpenseCreate(BaseModel):
    station_id:int=Field(gt=0)
    category:str=Field(min_length=2,max_length=40)
    label:str=Field(min_length=2,max_length=180)
    vendor:str|None=Field(default=None,max_length=160)
    description:str|None=Field(default=None,max_length=500)
    expense_date:date
    amount:int=Field(gt=0,le=2_000_000_000)
    receipt_name:str|None=Field(default=None,max_length=255)
    receipt_url:str|None=Field(default=None,max_length=500)

class ExpensePaymentCreate(BaseModel):
    amount:int=Field(gt=0,le=2_000_000_000)
    method:Literal["cash","wave","orange_money","mtn_money","moov_money","card","bank_transfer","other"]
    reference:str|None=Field(default=None,max_length=100)

def _station(user:User,station_id:int,db:Session):
    q=db.query(Station).filter(Station.id==station_id,Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None: q=q.filter(Station.id==user.station_id)
    if not q.first(): raise HTTPException(404,"Station introuvable ou non autorisée")

def _serialize(expense:Expense,db:Session):
    payments=db.query(ExpensePayment).filter(ExpensePayment.expense_id==expense.id).order_by(ExpensePayment.paid_at,ExpensePayment.id).all()
    paid=sum(p.amount for p in payments)
    return {"id":expense.id,"company_id":expense.company_id,"station_id":expense.station_id,
      "category":expense.category,"label":expense.label,"vendor":expense.vendor,"description":expense.description,
      "expense_date":expense.expense_date,"amount":expense.amount,"paid_amount":paid,"remaining_amount":expense.amount-paid,
      "status":"paid" if paid==expense.amount else "partial" if paid else "unpaid",
      "receipt_name":expense.receipt_name,"receipt_url":expense.receipt_url,"created_at":expense.created_at,
      "payments":[{"id":p.id,"amount":p.amount,"method":p.method,"reference":p.reference,"paid_at":p.paid_at} for p in payments]}

@router.get("/expenses")
def list_expenses(station_id:int|None=None,category:str|None=None,status:str|None=None,
    date_from:date|None=None,date_to:date|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Expense).filter(Expense.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Expense.station_id==user.station_id)
    elif station_id is not None: q=q.filter(Expense.station_id==station_id)
    if category: q=q.filter(Expense.category==category)
    if date_from: q=q.filter(Expense.expense_date>=date_from)
    if date_to: q=q.filter(Expense.expense_date<=date_to)
    rows=q.order_by(Expense.expense_date.desc(),Expense.id.desc()).limit(300).all()
    result=[_serialize(x,db) for x in rows]
    return [x for x in result if status is None or x["status"]==status]

@router.post("/expenses",status_code=201)
def create_expense(payload:ExpenseCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in ALLOWED_ROLES: raise HTTPException(403,"Droits de gestion des dépenses requis")
    _station(user,payload.station_id,db)
    if payload.category not in CATEGORIES: raise HTTPException(422,"Catégorie de dépense non reconnue")
    expense=Expense(company_id=user.company_id,station_id=payload.station_id,created_by=user.id,
      category=payload.category,label=payload.label.strip(),vendor=payload.vendor,description=payload.description,
      expense_date=payload.expense_date,amount=payload.amount,receipt_name=payload.receipt_name,receipt_url=payload.receipt_url)
    db.add(expense);db.commit();db.refresh(expense)
    return _serialize(expense,db)

@router.get("/expenses/summary")
def expense_summary(station_id:int|None=None,date_from:date|None=None,date_to:date|None=None,
    user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Expense).filter(Expense.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Expense.station_id==user.station_id)
    elif station_id is not None: q=q.filter(Expense.station_id==station_id)
    if date_from: q=q.filter(Expense.expense_date>=date_from)
    if date_to: q=q.filter(Expense.expense_date<=date_to)
    rows=q.all()
    total=sum(x.amount for x in rows)
    paid=db.query(func.coalesce(func.sum(ExpensePayment.amount),0)).filter(
      ExpensePayment.company_id==user.company_id,ExpensePayment.expense_id.in_([x.id for x in rows] or [-1])).scalar() or 0
    by_category={}
    for x in rows: by_category[x.category]=by_category.get(x.category,0)+x.amount
    return {"expenses_count":len(rows),"committed_amount":total,"paid_amount":int(paid),
      "remaining_amount":total-int(paid),"by_category":by_category}

@router.get("/expenses/{expense_id}")
def get_expense(expense_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Expense).filter(Expense.id==expense_id,Expense.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Expense.station_id==user.station_id)
    expense=q.first()
    if not expense: raise HTTPException(404,"Dépense introuvable")
    return _serialize(expense,db)

@router.post("/expenses/{expense_id}/payments",status_code=201)
def pay_expense(expense_id:int,payload:ExpensePaymentCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in ALLOWED_ROLES: raise HTTPException(403,"Droits de règlement requis")
    q=db.query(Expense).filter(Expense.id==expense_id,Expense.company_id==user.company_id)
    if user.station_id is not None: q=q.filter(Expense.station_id==user.station_id)
    expense=q.with_for_update().first()
    if not expense: raise HTTPException(404,"Dépense introuvable")
    paid=int(db.query(func.coalesce(func.sum(ExpensePayment.amount),0)).filter(ExpensePayment.expense_id==expense.id).scalar() or 0)
    if payload.amount>expense.amount-paid: raise HTTPException(422,"Le règlement dépasse le solde de la dépense")
    payment=ExpensePayment(expense_id=expense.id,company_id=user.company_id,station_id=expense.station_id,
      paid_by=user.id,amount=payload.amount,method=payload.method,reference=payload.reference)
    db.add(payment);db.commit();db.refresh(expense)
    return _serialize(expense,db)
