def _report_owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}


def test_financial_report_separates_revenue_collections_expenses_and_cashflow(client):
    h=_report_owner(client,"reportowner@example.com","RPT1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    service=client.post("/api/v1/services",headers=h,json={"code":"LAV1","name":"Lavage complet","category":"lavage","price":30000,"station_id":station})
    assert service.status_code==201,service.text
    ticket=client.post("/api/v1/tickets",headers=h,json={"station_id":station,"vehicle_type":"SUV","lines":[{"service_id":service.json()["id"],"quantity":1}]})
    assert ticket.status_code==201,ticket.text
    ticket_id=ticket.json()["id"]
    paid=client.post(f"/api/v1/tickets/{ticket_id}/payments",headers=h,json={"amount":10000,"method":"cash"})
    assert paid.status_code==201,paid.text
    expense=client.post("/api/v1/expenses",headers=h,json={"station_id":station,"category":"eau","label":"Facture eau","expense_date":"2026-11-20","amount":8000})
    assert expense.status_code==201,expense.text
    pay=client.post(f"/api/v1/expenses/{expense.json()['id']}/payments",headers=h,json={"amount":3000,"method":"cash"})
    assert pay.status_code==201,pay.text
    report=client.get("/api/v1/reports/financial?period=custom&start_date=2026-11-20&end_date=2026-11-20",headers=h)
    assert report.status_code==200,report.text
    data=report.json()
    assert data["revenue"]==30000
    assert data["collections"]==10000
    assert data["receivables_outstanding"]==20000
    assert data["expenses_committed"]==8000
    assert data["expense_disbursements"]==3000
    assert data["expense_liabilities_for_period"]==5000
    assert data["net_cash_flow"]==7000
    assert data["simplified_management_result"]==22000


def test_financial_report_is_tenant_and_station_scoped(client):
    a=_report_owner(client,"reporta@example.com","RPA1")
    b=_report_owner(client,"reportb@example.com","RPB1")
    report=client.get("/api/v1/reports/financial?period=custom&start_date=2026-11-20&end_date=2026-11-20",headers=b)
    assert report.status_code==200
    assert report.json()["revenue"]==0
    assert report.json()["collections"]==0
    assert report.json()["expenses_committed"]==0
    station_a=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    bad=client.get(f"/api/v1/reports/financial?station_id={station_a}",headers=b)
    assert bad.status_code==404
    invalid=client.get("/api/v1/reports/financial?period=custom&start_date=2026-11-21&end_date=2026-11-20",headers=a)
    assert invalid.status_code==422
