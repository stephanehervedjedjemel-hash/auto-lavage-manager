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


def test_station_profitability_report_compares_stations_and_isolates_tenants(client):
    owner = _report_owner(client, "stationcompare@example.com", "CMP1")
    stations = client.get("/api/v1/stations", headers=owner).json()
    first_id = stations[0]["id"]
    second = client.post("/api/v1/stations", headers=owner, json={
        "name": "Station secondaire", "code": "CMP2", "city": "Daloa"
    })
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    service = client.post("/api/v1/services", headers=owner, json={
        "code": "CMP-LAV", "name": "Lavage comparatif", "category": "lavage",
        "price": 25000, "station_id": first_id
    })
    assert service.status_code == 201, service.text
    ticket = client.post("/api/v1/tickets", headers=owner, json={
        "station_id": first_id, "vehicle_type": "SUV",
        "lines": [{"service_id": service.json()["id"], "quantity": 1}]
    })
    assert ticket.status_code == 201, ticket.text
    payment = client.post(f"/api/v1/tickets/{ticket.json()['id']}/payments",
        headers=owner, json={"amount": 15000, "method": "cash"})
    assert payment.status_code == 201, payment.text

    expense = client.post("/api/v1/expenses", headers=owner, json={
        "station_id": first_id, "category": "eau", "label": "Eau station 1",
        "expense_date": "2026-11-20", "amount": 5000
    })
    assert expense.status_code == 201, expense.text

    report = client.get(
        "/api/v1/reports/stations?period=custom&start_date=2026-11-20&end_date=2026-11-20",
        headers=owner,
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["stations_count"] == 2
    first = next(item for item in data["stations"] if item["station_id"] == first_id)
    second_data = next(item for item in data["stations"] if item["station_id"] == second_id)
    assert first["revenue"] == 25000
    assert first["collections"] == 15000
    assert first["expenses_committed"] == 5000
    assert first["simplified_management_result"] == 20000
    assert second_data["revenue"] == 0
    assert second_data["expenses_committed"] == 0

    other = _report_owner(client, "stationcompareother@example.com", "CMPX")
    foreign_station = client.get("/api/v1/stations", headers=other).json()[0]["id"]
    assert all(item["station_id"] != foreign_station for item in data["stations"])


def test_cancelled_ticket_is_removed_from_revenue_and_refund_from_collections(client):
    headers = _report_owner(client, "refundreport@example.com", "RFD1")
    station_id = client.get("/api/v1/stations", headers=headers).json()[0]["id"]
    service = client.post("/api/v1/services", headers=headers, json={
        "code": "RFD-WASH", "name": "Lavage remboursable", "price": 12000,
        "station_id": station_id,
    })
    assert service.status_code == 201, service.text
    ticket = client.post("/api/v1/tickets", headers=headers, json={
        "station_id": station_id, "vehicle_type": "Berline",
        "lines": [{"service_id": service.json()["id"], "quantity": 1}],
    })
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["id"]
    payment = client.post(f"/api/v1/tickets/{ticket_id}/payments", headers=headers, json={
        "amount": 10000, "method": "cash",
    })
    assert payment.status_code == 201, payment.text
    cancelled = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=headers, json={
        "reason": "Prestation non réalisée",
    })
    assert cancelled.status_code == 200, cancelled.text

    url = "/api/v1/reports/financial?period=custom&start_date=2026-11-20&end_date=2026-11-20"
    report = client.get(url, headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["revenue"] == 0
    assert data["collections"] == 0
    assert data["refunds_total"] == 10000
    assert data["receivables_outstanding"] == 0
    assert data["tickets_count"] == 0

    stations = client.get("/api/v1/reports/stations?period=custom&start_date=2026-11-20&end_date=2026-11-20",
        headers=headers)
    assert stations.status_code == 200, stations.text
    row = stations.json()["stations"][0]
    assert row["revenue"] == 0
    assert row["collections"] == 0
    assert row["refunds_total"] == 10000
    assert row["tickets_count"] == 0
