from io import BytesIO
from openpyxl import load_workbook

def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_payroll_pdf_xlsx_and_individual_bulletin_exports(client):
    h=_owner(client,"payrollexport@example.com","PEX1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    employee=client.post("/api/v1/employees",headers=h,json={"station_id":station,"employee_number":"EMP-PDF",
      "full_name":"Agent Exemple","job_title":"Agent de lavage","hire_date":"2026-01-01","base_salary":120000})
    assert employee.status_code==201,employee.text
    emp_id=employee.json()["id"]
    period=client.post("/api/v1/payroll",headers=h,json={"station_id":station,"period_type":"monthly",
      "start_date":"2026-10-01","end_date":"2026-10-31","lines":[{"employee_id":emp_id,"base_salary":120000,
      "bonuses":10000,"overtime_pay":5000,"deductions":2000,"employee_contributions":3000,
      "employer_contributions":6000,"advance_deduction":5000}]})
    assert period.status_code==201,period.text
    period_id=period.json()["id"];line_id=period.json()["lines"][0]["id"]
    validate=client.post(f"/api/v1/payroll/{period_id}/validate",headers=h)
    assert validate.status_code==200,validate.text
    payment=client.post(f"/api/v1/payroll/lines/{line_id}/payments",headers=h,json={"amount":50000,"method":"cash"})
    assert payment.status_code==201,payment.text
    for fmt,signature,ctype in [("pdf",b"%PDF","application/pdf"),("xlsx",b"PK","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]:
      response=client.get(f"/api/v1/payroll/{period_id}/export?format={fmt}",headers=h)
      assert response.status_code==200,response.text
      assert response.content.startswith(signature) and response.headers["content-type"].startswith(ctype)
    xlsx=client.get(f"/api/v1/payroll/{period_id}/export?format=xlsx",headers=h)
    wb=load_workbook(BytesIO(xlsx.content),read_only=True)
    rows=list(wb["Récapitulatif"].values)
    assert rows[3][0]=="EMP-PDF" and rows[3][10]==125000 and rows[3][11]==50000 and rows[3][12]==75000
    bulletin=client.get(f"/api/v1/payroll/lines/{line_id}/bulletin",headers=h)
    assert bulletin.status_code==200 and bulletin.content.startswith(b"%PDF")
    assert "bulletin_" in bulletin.headers["content-disposition"]

def test_payroll_exports_are_tenant_isolated(client):
    a=_owner(client,"payroll-expa@example.com","PEXA")
    b=_owner(client,"payroll-expb@example.com","PEXB")
    station=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    emp=client.post("/api/v1/employees",headers=a,json={"station_id":station,"employee_number":"EMP-X",
      "full_name":"Employé privé","job_title":"Agent","hire_date":"2026-01-01","base_salary":50000},)
    p=client.post("/api/v1/payroll",headers=a,json={"station_id":station,"period_type":"weekly",
      "start_date":"2026-10-01","end_date":"2026-10-07","lines":[{"employee_id":emp.json()["id"],"base_salary":50000}]})
    response=client.get(f"/api/v1/payroll/{p.json()['id']}/export?format=pdf",headers=b)
    assert response.status_code==404
