def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def _employee(client,headers,station_id):
    r=client.post("/api/v1/employees",headers=headers,json={"station_id":station_id,"employee_number":"EMP-1",
      "full_name":"Employé Pointage","job_title":"Agent","hire_date":"2026-01-01","base_salary":100000})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_attendance_presence_absence_leave_overtime_and_summary(client):
    h=_owner(client,"attendance@example.com","ATT1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    employee=_employee(client,h,station)
    present=client.post("/api/v1/attendance",headers=h,json={"employee_id":employee,"work_date":"2026-11-01",
      "status":"present","regular_hours":8,"overtime_hours":2,"late_minutes":15})
    assert present.status_code==201,present.text
    absent=client.post("/api/v1/attendance",headers=h,json={"employee_id":employee,"work_date":"2026-11-02","status":"absent"})
    leave=client.post("/api/v1/attendance",headers=h,json={"employee_id":employee,"work_date":"2026-11-03",
      "status":"leave","leave_type":"annual"})
    assert absent.status_code==201 and leave.status_code==201
    duplicate=client.post("/api/v1/attendance",headers=h,json={"employee_id":employee,"work_date":"2026-11-01","status":"present"})
    assert duplicate.status_code==409
    summary=client.get("/api/v1/attendance/summary?start_date=2026-11-01&end_date=2026-11-03",headers=h).json()
    assert (summary["present_count"],summary["absent_count"],summary["leave_count"],
      summary["overtime_hours"],summary["late_minutes"])==(1,1,1,2,15)

def test_attendance_tenant_isolation_and_invalid_status_hours(client):
    a=_owner(client,"attendance-a@example.com","ATA1")
    b=_owner(client,"attendance-b@example.com","ATB1")
    sa=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    employee=_employee(client,a,sa)
    hidden=client.post("/api/v1/attendance",headers=b,json={"employee_id":employee,"work_date":"2026-11-01","status":"present"})
    invalid=client.post("/api/v1/attendance",headers=a,json={"employee_id":employee,"work_date":"2026-11-01",
      "status":"absent","regular_hours":8})
    assert hidden.status_code==404 and invalid.status_code==422
    assert client.get("/api/v1/attendance",headers=b).json()==[]
