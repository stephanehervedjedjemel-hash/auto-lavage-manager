from datetime import date
from io import BytesIO
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Employee, PayrollPeriod, PayrollLine, PayrollPayment, AttendanceRecord, SalaryAdvance, AdvanceRepayment, Station, User

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


def _payroll_period_for_export(period_id,user,db):
    q=db.query(PayrollPeriod).filter(PayrollPeriod.id==period_id,PayrollPeriod.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(PayrollPeriod.station_id==user.station_id)
    period=q.first()
    if not period:raise HTTPException(404,"Période de paie introuvable")
    return period,_period_data(period,db)

def _payroll_line_for_export(line_id,user,db):
    q=db.query(PayrollLine).join(PayrollPeriod).filter(
      PayrollLine.id==line_id,PayrollPeriod.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(PayrollPeriod.station_id==user.station_id)
    line=q.first()
    if not line:raise HTTPException(404,"Bulletin introuvable")
    period,data=_payroll_period_for_export(line.payroll_period_id,user,db)
    item=next(x for x in data["lines"] if x["id"]==line.id)
    return period,data,item

def _bulletin_pdf(period,data,line):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm)
    styles=getSampleStyleSheet()
    story=[Paragraph("AUTO LAVAGE MANAGER",styles["Title"]),Paragraph("BULLETIN DE PAIE — ÉTAT DE GESTION",styles["Heading2"]),
      Paragraph(f"Période : {period.start_date} au {period.end_date} ({'Hebdomadaire' if period.period_type=='weekly' else 'Mensuelle'})",styles["Normal"]),
      Spacer(1,5*mm),Paragraph(f"<b>Salarié :</b> {line.employee_name}",styles["Normal"]),
      Paragraph(f"<b>Matricule :</b> {line.employee_number} · <b>Poste :</b> {line.job_title}",styles["Normal"]),
      Paragraph(f"<b>Statut de la paie :</b> {period.status}",styles["Normal"]),Spacer(1,5*mm)]
    rows=[["Éléments de rémunération","Montant (FCFA)"],
      ["Salaire de base",line.base_salary],["Primes",line.bonuses],["Heures supplémentaires valorisées",line.overtime_pay],
      ["Salaire brut",line.gross_salary],["Retenues",line.deductions],["Cotisations salariales",line.employee_contributions],
      ["Déduction des avances",line.advance_deduction],["NET À PAYER",line.net_due],
      ["Montant déjà réglé",data_line_paid(line.id,data)],["SOLDE RESTANT",max(line.net_due-data_line_paid(line.id,data),0)],
      ["Cotisations patronales (information)",line.employer_contributions]]
    table=Table([[a,(f"{b:,}".replace(","," ") if isinstance(b,int) else b)] for a,b in rows],colWidths=[110*mm,55*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174A6E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
      ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#D8E2E9")),
      ("PADDING",(0,0),(-1,-1),7),("ALIGN",(1,1),(1,-1),"RIGHT"),
      ("BACKGROUND",(0,9),(-1,9),colors.HexColor("#E7F0F6")),("FONTNAME",(0,9),(-1,9),"Helvetica-Bold")]))
    story.extend([table,Spacer(1,6*mm),Paragraph("Historique des règlements",styles["Heading3"])])
    pays=[["Date","Moyen","Référence","Montant (FCFA)"]]
    for p in next(x for x in data["lines"] if x["id"]==line.id)["payments"]:
      pays.append([str(p["paid_at"]),p["method"],p["reference"] or "—",f"{p['amount']:,}".replace(","," ")])
    if len(pays)==1:pays.append(["—","Aucun règlement","—","0"])
    pt=Table(pays,colWidths=[48*mm,35*mm,45*mm,37*mm],repeatRows=1)
    pt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E7F0F6")),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D8E2E9")),("PADDING",(0,0),(-1,-1),5),("FONTSIZE",(0,0),(-1,-1),8)]))
    story.extend([pt,Spacer(1,8*mm),Paragraph("Document de gestion généré par AUTO LAVAGE MANAGER. Les taux et règles légales doivent être validés avant utilisation comme bulletin réglementaire officiel.",styles["Italic"])])
    doc.build(story);output.seek(0);return output

def data_line_paid(line_id,data):
    line=next(x for x in data["lines"] if x["id"]==line_id)
    return line["paid_amount"]

@router.get("/payroll/{period_id}/export")
def export_payroll_period(period_id:int,format:Literal["pdf","xlsx"]="xlsx",
    user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    period,data=_payroll_period_for_export(period_id,user,db)
    filename=f"etat_paie_{period.start_date}_{period.end_date}"
    if format=="xlsx":
      from openpyxl import Workbook
      from openpyxl.styles import Font,PatternFill,Alignment
      from openpyxl.utils import get_column_letter
      wb=Workbook();ws=wb.active;ws.title="Récapitulatif"
      ws.append(["AUTO LAVAGE MANAGER — ÉTAT DE PAIE"])
      ws.append(["Période",str(period.start_date),"au",str(period.end_date),"Type",period.period_type,"Statut",period.status])
      ws.append(["Matricule","Salarié","Poste","Base","Primes","Heures sup.","Brut","Retenues","Cot. salariales","Avances","Net dû","Payé","Reste","Cot. patronales"])
      for x in data["lines"]:
        ws.append([x["employee_number"],x["employee_name"],x["job_title"],x["base_salary"],x["bonuses"],x["overtime_pay"],x["gross_salary"],x["deductions"],x["employee_contributions"],x["advance_deduction"],x["net_due"],x["paid_amount"],x["remaining_amount"],x["employer_contributions"]])
      pay=wb.create_sheet("Règlements");pay.append(["Matricule","Salarié","Date","Moyen","Référence","Montant FCFA"])
      for x in data["lines"]:
        for p in x["payments"]:pay.append([x["employee_number"],x["employee_name"],str(p["paid_at"]),p["method"],p["reference"] or "",p["amount"]])
      for sheet in wb.worksheets:
        sheet.freeze_panes="A3" if sheet.title=="Récapitulatif" else "A2";sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="174A6E")
        for col in sheet.columns:
          width=min(max(max(len(str(c.value or "")) for c in col)+2,12),38);sheet.column_dimensions[get_column_letter(col[0].column)].width=width
        for row in sheet.iter_rows():
          for cell in row:cell.alignment=Alignment(vertical="center")
      out=BytesIO();wb.save(out);out.seek(0)
      return StreamingResponse(out,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="{filename}.xlsx"'})
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=10*mm,leftMargin=10*mm,topMargin=12*mm,bottomMargin=12*mm)
    styles=getSampleStyleSheet()
    story=[Paragraph("AUTO LAVAGE MANAGER — ÉTAT RÉCAPITULATIF DE PAIE",styles["Title"]),
      Paragraph(f"Période : {period.start_date} au {period.end_date} · {period.period_type} · Statut : {period.status}",styles["Normal"]),
      Spacer(1,5*mm)]
    rows=[["Matricule","Salarié","Brut","Retenues","Cot. sal.","Avances","Net dû","Payé","Reste"]]
    for x in data["lines"]:
      rows.append([x["employee_number"],x["employee_name"][:24],*[f"{x[k]:,}".replace(","," ") for k in ("gross_salary","deductions","employee_contributions","advance_deduction","net_due","paid_amount","remaining_amount")]])
    if len(rows)==1:rows.append(["—","Aucun salarié","0","0","0","0","0","0","0"])
    table=Table(rows,repeatRows=1,colWidths=[23*mm,43*mm]+[22*mm]*7)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174A6E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D8E2E9")),("FONTSIZE",(0,0),(-1,-1),7),("PADDING",(0,0),(-1,-1),4)]))
    story.extend([table,Spacer(1,5*mm),Paragraph(f"Brut total : {data['gross_total']:,} FCFA · Net dû : {data['net_due_total']:,} FCFA · Réglé : {data['paid_total']:,} FCFA · Reste : {data['remaining_total']:,} FCFA".replace(","," "),styles["Normal"]),PageBreak()])
    for idx,x in enumerate(data["lines"]):
      line=db.query(PayrollLine).filter(PayrollLine.id==x["id"]).first()
      story.append(Paragraph(f"BULLETIN INDIVIDUEL — {x['employee_name']}",styles["Heading2"]))
      story.append(Paragraph(f"Matricule : {x['employee_number']} · Poste : {x['job_title']} · Période : {period.start_date} au {period.end_date}",styles["Normal"]))
      values=[["Élément","Montant FCFA"],["Salaire de base",x["base_salary"]],["Primes",x["bonuses"]],["Heures supplémentaires",x["overtime_pay"]],["Salaire brut",x["gross_salary"]],["Retenues",x["deductions"]],["Cotisations salariales",x["employee_contributions"]],["Déduction des avances",x["advance_deduction"]],["NET À PAYER",x["net_due"]],["Déjà réglé",x["paid_amount"]],["Reste à payer",x["remaining_amount"]],["Cotisations patronales (information)",x["employer_contributions"]]]
      t=Table([[a,(f"{v:,}".replace(","," ") if isinstance(v,int) else v)] for a,v in values],colWidths=[110*mm,55*mm])
      t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174A6E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#D8E2E9")),("PADDING",(0,0),(-1,-1),5),("ALIGN",(1,1),(1,-1),"RIGHT")]))
      story.extend([Spacer(1,4*mm),t,Spacer(1,3*mm),Paragraph("Document de gestion — règles légales et taux à valider avant usage officiel.",styles["Italic"])])
      if idx<len(data["lines"])-1:story.append(PageBreak())
    doc.build(story);out.seek(0)
    return StreamingResponse(out,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{filename}.pdf"'})

@router.get("/payroll/lines/{line_id}/bulletin")
def export_employee_bulletin(line_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    period,data,line=_payroll_line_for_export(line_id,user,db)
    record=db.query(PayrollLine).filter(PayrollLine.id==line_id).first()
    out=_bulletin_pdf(period,data,record)
    safe="".join(c for c in line["employee_number"] if c.isalnum() or c in "-_") or str(line_id)
    return StreamingResponse(out,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="bulletin_{safe}_{period.end_date}.pdf"'})


class AdvanceCreate(BaseModel):
    employee_id:int=Field(gt=0)
    amount:int=Field(gt=0,le=2_000_000_000)
    reason:str=Field(min_length=3,max_length=500)

class AdvanceDecision(BaseModel):
    note:str|None=Field(default=None,max_length=500)

class AdvanceRepaymentCreate(BaseModel):
    amount:int=Field(gt=0,le=2_000_000_000)
    reference:str|None=Field(default=None,max_length=100)
    note:str|None=Field(default=None,max_length=500)

def _advance_data(row,db):
    employee=db.query(Employee).filter(Employee.id==row.employee_id).first()
    repaid=int(db.query(func.coalesce(func.sum(AdvanceRepayment.amount),0)).filter(AdvanceRepayment.advance_id==row.id).scalar() or 0)
    return {"id":row.id,"employee_id":row.employee_id,"employee_number":employee.employee_number,
      "employee_name":employee.full_name,"station_id":row.station_id,"amount":row.amount,
      "repaid_amount":repaid,"remaining_amount":row.amount-repaid,"reason":row.reason,
      "status":row.status,"requested_at":row.requested_at,"decided_at":row.decided_at,
      "decision_note":row.decision_note,"repayments":[{"id":x.id,"amount":x.amount,"source":x.source,
      "reference":x.reference,"note":x.note,"repaid_at":x.repaid_at} for x in db.query(AdvanceRepayment).filter(
      AdvanceRepayment.advance_id==row.id).order_by(AdvanceRepayment.repaid_at).all()]}

@router.get("/advances")
def list_advances(status:Literal["pending","approved","partially_repaid","repaid","rejected"]|None=None,
                  station_id:int|None=None,employee_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(SalaryAdvance).filter(SalaryAdvance.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(SalaryAdvance.station_id==user.station_id)
    elif station_id is not None:q=q.filter(SalaryAdvance.station_id==station_id)
    if status:q=q.filter(SalaryAdvance.status==status)
    if employee_id:q=q.filter(SalaryAdvance.employee_id==employee_id)
    return [_advance_data(x,db) for x in q.order_by(SalaryAdvance.requested_at.desc()).limit(500).all()]

@router.get("/advances/summary")
def advance_summary(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(SalaryAdvance).filter(SalaryAdvance.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(SalaryAdvance.station_id==user.station_id)
    rows=q.all()
    items=[_advance_data(x,db) for x in rows]
    return {"requests_count":len(rows),"pending_amount":sum(x["amount"] for x in items if x["status"]=="pending"),
      "approved_amount":sum(x["amount"] for x in items if x["status"] in ("approved","partially_repaid","repaid")),
      "outstanding_amount":sum(x["remaining_amount"] for x in items if x["status"] in ("approved","partially_repaid"))}

@router.post("/advances",status_code=201)
def request_advance(payload:AdvanceCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    q=db.query(Employee).filter(Employee.id==payload.employee_id,Employee.company_id==user.company_id,Employee.is_active.is_(True))
    if user.station_id is not None:q=q.filter(Employee.station_id==user.station_id)
    employee=q.first()
    if not employee:raise HTTPException(404,"Salarié actif introuvable ou non autorisé")
    row=SalaryAdvance(company_id=user.company_id,station_id=employee.station_id,employee_id=employee.id,
      requested_by=user.id,amount=payload.amount,reason=payload.reason,status="pending")
    db.add(row);db.commit();db.refresh(row)
    return _advance_data(row,db)

@router.post("/advances/{advance_id}/approve")
def approve_advance(advance_id:int,payload:AdvanceDecision,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Validation des avances réservée aux responsables")
    q=db.query(SalaryAdvance).filter(SalaryAdvance.id==advance_id,SalaryAdvance.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(SalaryAdvance.station_id==user.station_id)
    row=q.with_for_update().first()
    if not row:raise HTTPException(404,"Demande d'avance introuvable")
    if row.status!="pending":raise HTTPException(409,"Cette demande a déjà été traitée")
    row.status="approved";row.decided_by=user.id;row.decided_at=func.now();row.decision_note=payload.note
    db.commit();db.refresh(row)
    return _advance_data(row,db)

@router.post("/advances/{advance_id}/reject")
def reject_advance(advance_id:int,payload:AdvanceDecision,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Rejet des avances réservé aux responsables")
    q=db.query(SalaryAdvance).filter(SalaryAdvance.id==advance_id,SalaryAdvance.company_id==user.company_id)
    if user.station_id is not None:q=q.filter(SalaryAdvance.station_id==user.station_id)
    row=q.with_for_update().first()
    if not row:raise HTTPException(404,"Demande d'avance introuvable")
    if row.status!="pending":raise HTTPException(409,"Cette demande a déjà été traitée")
    row.status="rejected";row.decided_by=user.id;row.decided_at=func.now();row.decision_note=payload.note
    db.commit();db.refresh(row)
    return _advance_data(row,db)

@router.post("/advances/{advance_id}/repayments",status_code=201)
def repay_advance(advance_id:int,payload:AdvanceRepaymentCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role not in MANAGERS:raise HTTPException(403,"Enregistrement des remboursements réservé aux responsables")
    q=db.query(SalaryAdvance).filter(SalaryAdvance.id==advance_id,SalaryAdvance.company_id==user.company_id,
      SalaryAdvance.status.in_(["approved","partially_repaid"]))
    if user.station_id is not None:q=q.filter(SalaryAdvance.station_id==user.station_id)
    row=q.with_for_update().first()
    if not row:raise HTTPException(404,"Avance approuvée introuvable")
    paid=int(db.query(func.coalesce(func.sum(AdvanceRepayment.amount),0)).filter(AdvanceRepayment.advance_id==row.id).scalar() or 0)
    if payload.amount>row.amount-paid:raise HTTPException(422,"Le remboursement dépasse le solde de l'avance")
    db.add(AdvanceRepayment(advance_id=row.id,company_id=user.company_id,station_id=row.station_id,
      recorded_by=user.id,amount=payload.amount,source="manual",reference=payload.reference,note=payload.note))
    row.status="repaid" if payload.amount==row.amount-paid else "partially_repaid"
    db.commit();db.refresh(row)
    return _advance_data(row,db)
