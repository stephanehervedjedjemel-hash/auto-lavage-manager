def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_salary_advance_request_approval_partial_and_full_repayment(client):
    h=_owner(client,"advance@example.com","ADV1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    emp=client.post("/api/v1/employees",headers=h,json={"station_id":station,"employee_number":"ADV-1",
      "full_name":"Employé Avance","job_title":"Agent","hire_date":"2026-01-01","base_salary":100000}).json()
    req=client.post("/api/v1/advances",headers=h,json={"employee_id":emp["id"],"amount":30000,"reason":"Besoin personnel"})
    assert req.status_code==201 and req.json()["status"]=="pending"
    approved=client.post(f"/api/v1/advances/{req.json()['id']}/approve",headers=h,json={"note":"Accord"})
    assert approved.status_code==200 and approved.json()["remaining_amount"]==30000
    first=client.post(f"/api/v1/advances/{req.json()['id']}/repayments",headers=h,json={"amount":10000})
    assert first.status_code==201 and first.json()["status"]=="partially_repaid"
    over=client.post(f"/api/v1/advances/{req.json()['id']}/repayments",headers=h,json={"amount":25000})
    assert over.status_code==422
    final=client.post(f"/api/v1/advances/{req.json()['id']}/repayments",headers=h,json={"amount":20000})
    assert final.status_code==201 and final.json()["status"]=="repaid" and final.json()["remaining_amount"]==0
    summary=client.get("/api/v1/advances/summary",headers=h).json()
    assert summary["outstanding_amount"]==0 and summary["approved_amount"]==30000

def test_advance_tenant_isolation_and_reject(client):
    a=_owner(client,"advance-a@example.com","ADA1");b=_owner(client,"advance-b@example.com","ADB1")
    station=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    emp=client.post("/api/v1/employees",headers=a,json={"station_id":station,"employee_number":"ADV-X",
      "full_name":"Employé Privé","job_title":"Agent","hire_date":"2026-01-01","base_salary":50000}).json()
    req=client.post("/api/v1/advances",headers=a,json={"employee_id":emp["id"],"amount":10000,"reason":"Test"}).json()
    assert client.post(f"/api/v1/advances/{req['id']}/approve",headers=b,json={}).status_code==404
    rejected=client.post(f"/api/v1/advances/{req['id']}/reject",headers=a,json={"note":"Refus"})
    assert rejected.status_code==200 and rejected.json()["status"]=="rejected"
