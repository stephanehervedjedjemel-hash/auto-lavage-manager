def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}
def test_ticket_creation_and_split_payments(client):
    headers=_owner(client,"ticketowner@example.com","TK1")
    service=client.post("/api/v1/services",headers=headers,json={"code":"FULL","name":"Lavage complet","price":5000})
    assert service.status_code==201,service.text
    station=client.get("/api/v1/stations",headers=headers).json()[0]
    ticket=client.post("/api/v1/tickets",headers=headers,json={"station_id":station["id"],
      "customer_name":"Client test","vehicle_type":"Berline","vehicle_registration":"AB-123-CD",
      "lines":[{"service_id":service.json()["id"],"quantity":2}]})
    assert ticket.status_code==201,ticket.text
    body=ticket.json()
    assert body["total"]==10000 and body["remaining_amount"]==10000 and body["status"]=="unpaid"
    p1=client.post(f"/api/v1/tickets/{body['id']}/payments",headers=headers,json={"amount":4000,"method":"cash"})
    assert p1.status_code==201,p1.text
    p2=client.post(f"/api/v1/tickets/{body['id']}/payments",headers=headers,json={"amount":6000,"method":"wave"})
    assert p2.status_code==201,p2.text
    final=client.get(f"/api/v1/tickets/{body['id']}",headers=headers).json()
    assert final["paid_amount"]==10000 and final["remaining_amount"]==0 and final["status"]=="paid"
def test_ticket_rejects_cross_tenant_and_overpayment(client):
    h1=_owner(client,"ticketone@example.com","TK2")
    h2=_owner(client,"tickettwo@example.com","TK3")
    service=client.post("/api/v1/services",headers=h1,json={"code":"WASH","name":"Lavage","price":2500}).json()
    station=client.get("/api/v1/stations",headers=h1).json()[0]
    ticket=client.post("/api/v1/tickets",headers=h1,json={"station_id":station["id"],"vehicle_type":"SUV",
      "lines":[{"service_id":service["id"],"quantity":1}]}).json()
    assert client.get(f"/api/v1/tickets/{ticket['id']}",headers=h2).status_code==404
    assert client.post(f"/api/v1/tickets/{ticket['id']}/payments",headers=h2,json={"amount":2500,"method":"cash"}).status_code==404
    assert client.post(f"/api/v1/tickets/{ticket['id']}/payments",headers=h1,json={"amount":3000,"method":"cash"}).status_code==422
