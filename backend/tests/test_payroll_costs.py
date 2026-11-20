def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_payroll_costs_by_station_and_no_expense_double_count(client):
    h=_owner(client,"paycost@example.com","PCST")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    emp=client.post("/api/v1/employees",headers=h,json={"station_id":station,"employee_number":"PC-1",
      "full_name":"Employé Coût","job_title":"Agent","hire_date":"2026-01-01","base_salary":100000}).json()
    p=client.post("/api/v1/payroll",headers=h,json={"station_id":station,"period_type":"monthly",
      "start_date":"2026-10-01","end_date":"2026-10-31","lines":[{"employee_id":emp["id"],"base_salary":100000,
      "employer_contributions":12000}]}).json()
    client.post(f"/api/v1/payroll/{p['id']}/validate",headers=h)
    data=client.get("/api/v1/payroll/costs?start_date=2026-10-01&end_date=2026-10-31",headers=h)
    assert data.status_code==200,data.text
    assert data.json()["totals"]["total_employer_cost"]==112000
    assert data.json()["stations"][0]["station_id"]==station
    financial=client.get("/api/v1/reports/financial?period=custom&start_date=2026-10-01&end_date=2026-10-31",headers=h).json()
    assert financial["expenses_committed"]==0
