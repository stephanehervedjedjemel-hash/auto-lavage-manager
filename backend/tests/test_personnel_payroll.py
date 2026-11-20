def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def _employee(client,headers,station_id,number="EMP-001"):
    r=client.post("/api/v1/employees",headers=headers,json={"station_id":station_id,"employee_number":number,
      "full_name":"Employé Test","job_title":"Agent de lavage","contract_type":"permanent",
      "hire_date":"2026-01-01","salary_basis":"monthly","base_salary":100000})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_employee_register_and_payroll_validation_and_partial_payments(client):
    h=_owner(client,"payroll-owner@example.com","PAY1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    employee=_employee(client,h,station)
    p=client.post("/api/v1/payroll",headers=h,json={"station_id":station,"period_type":"monthly",
      "start_date":"2026-10-01","end_date":"2026-10-31","lines":[{"employee_id":employee,"base_salary":100000,
      "bonuses":10000,"overtime_pay":5000,"deductions":2000,"employee_contributions":0,
      "employer_contributions":5000,"advance_deduction":10000}]})
    assert p.status_code==201,p.text
    data=p.json();line=data["lines"][0]
    assert (line["gross_salary"],line["net_due"],data["employer_contributions_total"])==(115000,103000,5000)
    assert data["status"]=="draft"
    assert client.post(f"/api/v1/payroll/lines/{line['id']}/payments",headers=h,json={"amount":1000,"method":"cash"}).status_code==404
    validated=client.post(f"/api/v1/payroll/{data['id']}/validate",headers=h)
    assert validated.status_code==200 and validated.json()["status"]=="validated"
    paid=client.post(f"/api/v1/payroll/lines/{line['id']}/payments",headers=h,json={"amount":50000,"method":"wave","reference":"TX-1"})
    assert paid.status_code==201 and paid.json()["remaining_amount"]==53000
    over=client.post(f"/api/v1/payroll/lines/{line['id']}/payments",headers=h,json={"amount":53001,"method":"cash"})
    assert over.status_code==422
    rest=client.post(f"/api/v1/payroll/lines/{line['id']}/payments",headers=h,json={"amount":53000,"method":"cash"})
    assert rest.status_code==201
    listed=client.get("/api/v1/payroll",headers=h).json()[0]
    assert listed["status"]=="paid" and listed["paid_total"]==103000

def test_employee_and_payroll_tenant_station_isolation(client):
    a=_owner(client,"payroll-a@example.com","PYA1")
    b=_owner(client,"payroll-b@example.com","PYB1")
    station_a=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    station_b=client.get("/api/v1/stations",headers=b).json()[0]["id"]
    employee=_employee(client,a,station_a,"PRIVATE-1")
    assert client.get("/api/v1/employees",headers=b).json()==[]
    invalid=client.post("/api/v1/payroll",headers=b,json={"station_id":station_b,"period_type":"weekly",
      "start_date":"2026-10-01","end_date":"2026-10-07","lines":[{"employee_id":employee,"base_salary":10000}]})
    assert invalid.status_code==422
    duplicate=client.post("/api/v1/employees",headers=a,json={"station_id":station_a,"employee_number":"PRIVATE-1",
      "full_name":"Autre salarié","job_title":"Agent","hire_date":"2026-01-01","base_salary":50000})
    assert duplicate.status_code==409

def test_payroll_negative_net_and_invalid_dates(client):
    h=_owner(client,"payroll-c@example.com","PYC1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    employee=_employee(client,h,station)
    negative=client.post("/api/v1/payroll",headers=h,json={"station_id":station,"period_type":"weekly",
      "start_date":"2026-10-08","end_date":"2026-10-07","lines":[{"employee_id":employee,"base_salary":1000}]})
    assert negative.status_code==422
