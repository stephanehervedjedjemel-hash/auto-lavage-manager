from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Employee, PayrollPeriod, PayrollLine, PayrollPayment, AttendanceRecord, Station, User

router=APIRouter()
MANAGERS={"company_admin","station_manager"}
PAYMENT_METHODS={"cash","wave","orange_money","mtn_money","moov_money","card","bank_transfer","other"}

class EmployeeCreate(BaseModel):
    station_id:int=Field(gt=0)
    employee_number:str=Field(min_length=1,max_length=40)
    full_name:str=Field(min_length=2,max_length=180)
    phone:str|None=Field(default=None,max_length=40)
    email:str|None=Field(default=None,max_length=255)
    job_title:str=Field(min_length=2,max_length=120)
    contract_type:Literal["permanent","fixed_term","temporary","daily","apprentice","other"]="permanent"
    hire_date:date
    end_date:date|None=None
    salary_basis:Literal["weekly","monthly"]="monthly"
    base_salary:int=Field(ge=0,le=2_000_000_000)
    @model_validator(mode="after")
    def dates(self):
        if self.end_date and self.end_date<self.hire_date: raise ValueError("La fin du contrat précède l'embauche")
        return self

class EmployeeStatus(BaseModel):
    is_active:bool

class PayrollLineInput(BaseModel):
    employee_id:int=Field(gt=0)
    base_salary:int=Field(ge=0,le=2_000_000_000)
    bonuses:int=Field(default=0,ge=0,le=2_000_000_000)
    overtime_pay:int=Field(default=0,ge=0,le=2_000_000_000)
    deductions:int=Field(default=0,ge=0,le=2_000_000_000)
    employee_contributions:int=Field(default=0,ge=0,le=2_000_000_000)
    employer_contributions:int=Field(default=0,ge=0,le=2_000_000_000)
    advance_deduction:int=Field(default=0,ge=0,le=2_000_000_000)
    note:str|None=Field(default=None,max_length=500)

class PayrollCreate(BaseModel):
    station_id:int=Field(gt=0)
    period_type:Literal["weekly","monthly"]
    start_date:date
    end_date:date
    lines:list[PayrollLineInput]=Field(min_length=1,max_length=300)
    @model_validator(mode="after")
    def dates(self):
        if self.end_date<self.start_date: raise ValueError("La fin de période précède le début")
        ids=[x.employee_id for x in self.lines]
        if len(ids)!=len(set(ids)): raise ValueError("Un salarié ne peut apparaître qu'une fois dans la paie")
        return self

class PayrollPaymentCreate(BaseModel):
    amount:int=Field(gt=0,le=2_000_000_000)
    method:Literal["cash","wave","orange_money","mtn_money","moov_money","card","bank_transfer","other"]
    reference:str|None=Field(default=None,max_length=100)

def _station(user,station_id,db):
    q=db.query(Station).filter(Station.id==station_id,Station.company_id==user.company_id,Station.is_active.is_(True))
    if user.station_id is not None:q=q.filter(Station.id==user.station_id)
    if not q.first():raise HTTPException(404,"Station introuvable ou non autorisée")

def _line_data(line,db):
    payments=db.query(PayrollPayment).filter(PayrollPayment.payroll_line_id==line.id).order_by(PayrollPayment.paid_at,PayrollPayment.id).all()
    paid=sum(p.amount for p in payments)
    return {"id":line.id,"employee_id":line.employee_id,"employee_number":line.employee_number,
      "employee_name":line.employee_name,"job_title":line.job_title,"base_salary":line.base_salary,
      "bonuses":line.bonuses,"overtime_pay":line.overtime_pay,"gross_salary":line.gross_salary,
      "deductions":line.deductions,"employee_contributions":line.employee_contributions,
      "employer_contributions":line.employer_contributions,"advance_deduction":line.advance_deduction,
      "net_due":line.net_due,"paid_amount":paid,"remaining_amount":line.net_due-paid,"note":line.note,
      "payments":[{"id":p.id,"amount":p.amount,"method":p.method,"reference":p.reference,"paid_at":p.paid_at} for p in payments]}

def _period_data(period,db):
    lines=db.query(PayrollLine).filter(PayrollLine.payroll_period_id==period.id).order_by(PayrollLine.employee_name).all()
    items=[_line_data(x,db) for x in lines]
    return {"id":period.id,"station_id":period.station_id,"period_type":period.period_type,
      "start_date":period.start_date,"end_date":period.end_date,"status":period.status,
      "gross_total":sum(x["gross_salary"] for x in items),
      "employee_contributions_total":sum(x["employee_contributions"] for x in items),
      "employer_contributions_total":sum(x["employer_contributions"] for x in items),
      "net_due_total":sum(x["net_due"] for x in items),
      "paid_total":sum(x["paid_amount"] for x in items),
      "remaining_total":sum(x["remaining_amount"] for x in items),"lines":items,
      "validated_at":period.validated_at,"created_at":period.created_at}

@router.get("/employees")
def list_employees(station_id:int|None=None,include_inactive:bool=False,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Employee).filter(Employee.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(Employee.station_id==user.station_id)
    elif station_id is not None:q=q.filter(Employee.station_id==station_id)
    if not include_inactive:q=q.filter(Employee.is_active.is_(True))
    return [{"id":x.id,"station_id":x.station_id,"employee_number":x.employee_number,"full_name":x.full_name,
      "phone":x.phone,"email":x.email,"job_title":x.job_title,"contract_type":x.contract_type,
      "hire_date":x.hire_date,"end_date":x.end_date,"salary_basis":x.salary_basis,
      "base_salary":x.base_salary,"is_active":x.is_active,"created_at":x.created_at}
      for x in q.order_by(Employee.full_name).limit(500).all()]

@router.post("/employees",status_code=201)
def create_employee(payload:EmployeeCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de gestion du personnel requis")
    _station(user,payload.station_id,db)
    number=payload.employee_number.strip()
    if db.query(Employee).filter(Employee.company_id==user.company_id,Employee.employee_number==number).first():
        raise HTTPException(409,"Ce matricule existe déjà dans votre entreprise")
    row=Employee(company_id=user.company_id,station_id=payload.station_id,created_by=user.id,
      employee_number=number,full_name=payload.full_name.strip(),phone=payload.phone,email=payload.email,
      job_title=payload.job_title.strip(),contract_type=payload.contract_type,hire_date=payload.hire_date,
      end_date=payload.end_date,salary_basis=payload.salary_basis,base_salary=payload.base_salary)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"employee_number":row.employee_number,"full_name":row.full_name,"station_id":row.station_id}

@router.patch("/employees/{employee_id}/status")
def employee_status(employee_id:int,payload:EmployeeStatus,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de gestion du personnel requis")
    q=db.query(Employee).filter(Employee.id==employee_id,Employee.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(Employee.station_id==user.station_id)
    row=q.first()
    if not row:raise HTTPException(404,"Salarié introuvable")
    row.is_active=payload.is_active;db.commit()
    return {"id":row.id,"is_active":row.is_active}

@router.get("/payroll")
def list_payroll(station_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(PayrollPeriod).filter(PayrollPeriod.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(PayrollPeriod.station_id==user.station_id)
    elif station_id is not None:q=q.filter(PayrollPeriod.station_id==station_id)
    return [_period_data(x,db) for x in q.order_by(PayrollPeriod.start_date.desc()).limit(100).all()]

@router.post("/payroll",status_code=201)
def create_payroll(payload:PayrollCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de préparation de la paie requis")
    _station(user,payload.station_id,db)
    period=PayrollPeriod(company_id=user.company_id,station_id=payload.station_id,created_by=user.id,
      period_type=payload.period_type,start_date=payload.start_date,end_date=payload.end_date,status="draft")
    db.add(period);db.flush()
    for item in payload.lines:
        q=db.query(Employee).filter(Employee.id==item.employee_id,Employee.company_id==user.company_id,
          Employee.station_id==payload.station_id,Employee.is_active.is_(True))
        employee=q.first()
        if not employee:
            db.rollback();raise HTTPException(422,f"Salarié {item.employee_id} absent, inactif ou hors de cette station")
        gross=item.base_salary+item.bonuses+item.overtime_pay
        net=gross-item.deductions-item.employee_contributions-item.advance_deduction
        if net<0:
            db.rollback();raise HTTPException(422,f"Le net à payer est négatif pour {employee.full_name}")
        db.add(PayrollLine(payroll_period_id=period.id,employee_id=employee.id,
          employee_number=employee.employee_number,employee_name=employee.full_name,job_title=employee.job_title,
          base_salary=item.base_salary,bonuses=item.bonuses,overtime_pay=item.overtime_pay,gross_salary=gross,
          deductions=item.deductions,employee_contributions=item.employee_contributions,
          employer_contributions=item.employer_contributions,advance_deduction=item.advance_deduction,
          net_due=net,note=item.note))
    db.commit();db.refresh(period)
    return _period_data(period,db)

@router.post("/payroll/{period_id}/validate")
def validate_payroll(period_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de validation de la paie requis")
    q=db.query(PayrollPeriod).filter(PayrollPeriod.id==period_id,PayrollPeriod.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(PayrollPeriod.station_id==user.station_id)
    period=q.with_for_update().first()
    if not period:raise HTTPException(404,"Période de paie introuvable")
    if period.status!="draft":raise HTTPException(409,"Seule une paie en brouillon peut être validée")
    period.status="validated";period.validated_by=user.id;period.validated_at=func.now()
    db.commit();db.refresh(period)
    return _period_data(period,db)

@router.post("/payroll/lines/{line_id}/payments",status_code=201)
def pay_payroll_line(line_id:int,payload:PayrollPaymentCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de règlement de la paie requis")
    q=db.query(PayrollLine).join(PayrollPeriod).filter(PayrollLine.id==line_id,
      PayrollPeriod.company_id==user.company_id,PayrollPeriod.status.in_(["validated","paid"]))
    if user.station_id is not None:q=q.filter(PayrollPeriod.station_id==user.station_id)
    line=q.with_for_update().first()
    if not line:raise HTTPException(404,"Ligne de paie validée introuvable")
    paid=int(db.query(func.coalesce(func.sum(PayrollPayment.amount),0)).filter(PayrollPayment.payroll_line_id==line.id).scalar() or 0)
    if payload.amount>line.net_due-paid:raise HTTPException(422,"Le règlement dépasse le net restant à payer")
    period=db.query(PayrollPeriod).filter(PayrollPeriod.id==line.payroll_period_id).first()
    db.add(PayrollPayment(payroll_line_id=line.id,company_id=user.company_id,station_id=period.station_id,
      paid_by=user.id,amount=payload.amount,method=payload.method,reference=payload.reference))
    db.flush()
    all_lines=db.query(PayrollLine).filter(PayrollLine.payroll_period_id==period.id).all()
    totals={x.id:x.net_due for x in all_lines}
    paid_rows=db.query(PayrollPayment).filter(PayrollPayment.payroll_line_id.in_(list(totals) or [-1])).all()
    if all(sum(p.amount for p in paid_rows if p.payroll_line_id==lid)>=due for lid,due in totals.items()):
        period.status="paid"
    db.commit();db.refresh(line)
    return _line_data(line,db)


class AttendanceCreate(BaseModel):
    employee_id:int=Field(gt=0)
    work_date:date
    status:Literal["present","absent","leave","permission","rest"]="present"
    regular_hours:int=Field(default=0,ge=0,le=24)
    overtime_hours:int=Field(default=0,ge=0,le=24)
    late_minutes:int=Field(default=0,ge=0,le=1440)
    leave_type:Literal["annual","sick","exceptional","unpaid","other"]|None=None
    note:str|None=Field(default=None,max_length=500)
    @model_validator(mode="after")
    def validate_record(self):
        if self.status!="present" and (self.regular_hours or self.overtime_hours or self.late_minutes):
            raise ValueError("Les heures et retards ne sont renseignés que pour une présence")
        if self.status!="leave" and self.leave_type is not None:
            raise ValueError("Le type de congé ne concerne qu'une absence pour congé")
        return self

def _attendance_data(row,employee):
    return {"id":row.id,"employee_id":row.employee_id,"employee_number":employee.employee_number,
      "employee_name":employee.full_name,"job_title":employee.job_title,"station_id":row.station_id,
      "work_date":row.work_date,"status":row.status,"regular_hours":row.regular_hours,
      "overtime_hours":row.overtime_hours,"late_minutes":row.late_minutes,
      "leave_type":row.leave_type,"note":row.note,"created_at":row.created_at}

@router.get("/attendance")
def list_attendance(start_date:date|None=None,end_date:date|None=None,station_id:int|None=None,
                    employee_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(AttendanceRecord,Employee).join(Employee,Employee.id==AttendanceRecord.employee_id).filter(
      AttendanceRecord.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(AttendanceRecord.station_id==user.station_id)
    elif station_id is not None:q=q.filter(AttendanceRecord.station_id==station_id)
    if start_date:q=q.filter(AttendanceRecord.work_date>=start_date)
    if end_date:q=q.filter(AttendanceRecord.work_date<=end_date)
    if employee_id:q=q.filter(AttendanceRecord.employee_id==employee_id)
    return [_attendance_data(r,e) for r,e in q.order_by(AttendanceRecord.work_date.desc(),Employee.full_name).limit(1000).all()]

@router.get("/attendance/summary")
def attendance_summary(start_date:date|None=None,end_date:date|None=None,station_id:int|None=None,
                       user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(AttendanceRecord).filter(AttendanceRecord.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(AttendanceRecord.station_id==user.station_id)
    elif station_id is not None:q=q.filter(AttendanceRecord.station_id==station_id)
    if start_date:q=q.filter(AttendanceRecord.work_date>=start_date)
    if end_date:q=q.filter(AttendanceRecord.work_date<=end_date)
    rows=q.all()
    return {"records_count":len(rows),"present_count":sum(x.status=="present" for x in rows),
      "absent_count":sum(x.status=="absent" for x in rows),"leave_count":sum(x.status=="leave" for x in rows),
      "permission_count":sum(x.status=="permission" for x in rows),"rest_count":sum(x.status=="rest" for x in rows),
      "overtime_hours":sum(x.overtime_hours for x in rows),"late_minutes":sum(x.late_minutes for x in rows)}

@router.post("/attendance",status_code=201)
def create_attendance(payload:AttendanceCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de gestion du pointage requis")
    q=db.query(Employee).filter(Employee.id==payload.employee_id,Employee.company_id==user.company_id,
      Employee.is_active.is_(True))
    if user.station_id is not None:q=q.filter(Employee.station_id==user.station_id)
    employee=q.first()
    if not employee:raise HTTPException(404,"Salarié actif introuvable ou non autorisé")
    if db.query(AttendanceRecord).filter(AttendanceRecord.company_id==user.company_id,
      AttendanceRecord.employee_id==employee.id,AttendanceRecord.work_date==payload.work_date).first():
        raise HTTPException(409,"Un pointage existe déjà pour ce salarié à cette date")
    row=AttendanceRecord(company_id=user.company_id,station_id=employee.station_id,employee_id=employee.id,
      created_by=user.id,work_date=payload.work_date,status=payload.status,regular_hours=payload.regular_hours,
      overtime_hours=payload.overtime_hours,late_minutes=payload.late_minutes,leave_type=payload.leave_type,note=payload.note)
    db.add(row);db.commit();db.refresh(row)
    return _attendance_data(row,employee)

@router.patch("/attendance/{record_id}")
def update_attendance(record_id:int,payload:AttendanceCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Droits de correction du pointage requis")
    q=db.query(AttendanceRecord).filter(AttendanceRecord.id==record_id,AttendanceRecord.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(AttendanceRecord.station_id==user.station_id)
    row=q.first()
    if not row:raise HTTPException(404,"Pointage introuvable")
    employee=db.query(Employee).filter(Employee.id==payload.employee_id,Employee.company_id==user.company_id,
      Employee.station_id==row.station_id).first()
    if not employee:raise HTTPException(422,"Le salarié doit appartenir à la même station")
    duplicate=db.query(AttendanceRecord).filter(AttendanceRecord.company_id==user.company_id,
      AttendanceRecord.employee_id==employee.id,AttendanceRecord.work_date==payload.work_date,
      AttendanceRecord.id!=row.id).first()
    if duplicate:raise HTTPException(409,"Un pointage existe déjà pour ce salarié à cette date")
    for key in ("employee_id","work_date","status","regular_hours","overtime_hours","late_minutes","leave_type","note"):
        setattr(row,key,getattr(payload,key))
    db.commit();db.refresh(row)
    return _attendance_data(row,employee)
