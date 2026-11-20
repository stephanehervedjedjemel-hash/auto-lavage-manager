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


def test_ticket_cancellation_refunds_every_payment_and_is_idempotent(client):
    headers = _owner(client, "cancelowner@example.com", "CAN1")
    service = client.post("/api/v1/services", headers=headers,
        json={"code": "CANCEL", "name": "Lavage annulation", "price": 5000})
    assert service.status_code == 201, service.text
    station = client.get("/api/v1/stations", headers=headers).json()[0]
    ticket = client.post("/api/v1/tickets", headers=headers, json={
        "station_id": station["id"], "vehicle_type": "Berline",
        "lines": [{"service_id": service.json()["id"], "quantity": 2}],
    })
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["id"]

    payment = client.post(f"/api/v1/tickets/{ticket_id}/payments", headers=headers,
        json={"amount": 4000, "method": "cash", "reference": "CAISSE-001"})
    assert payment.status_code == 201, payment.text

    cancelled = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=headers,
        json={"reason": "Erreur de saisie du véhicule"})
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["paid_amount"] == 4000
    assert body["refunded_amount"] == 4000
    assert len(body["refunds"]) == 1
    assert body["refunds"][0]["amount"] == 4000
    assert body["refunds"][0]["method"] == "cash"
    assert body["refunds"][0]["reason"] == "Erreur de saisie du véhicule"

    duplicate = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=headers,
        json={"reason": "Nouvelle tentative d'annulation"})
    assert duplicate.status_code == 409
    blocked_payment = client.post(f"/api/v1/tickets/{ticket_id}/payments", headers=headers,
        json={"amount": 1000, "method": "cash"})
    assert blocked_payment.status_code == 409


def test_operator_cannot_cancel_ticket(client):
    headers = _owner(client, "canceladmin@example.com", "CAN2")
    station = client.get("/api/v1/stations", headers=headers).json()[0]
    user = client.post("/api/v1/users", headers=headers, json={
        "full_name": "Agent caisse", "email": "canceloperator@example.com",
        "password": "MotDePasseAgentTresSolide123", "role": "operator",
        "station_id": station["id"],
    })
    assert user.status_code == 201, user.text
    login = client.post("/api/v1/auth/login", json={
        "email": "canceloperator@example.com", "password": "MotDePasseAgentTresSolide123",
    })
    assert login.status_code == 200, login.text
    operator_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    service = client.post("/api/v1/services", headers=headers,
        json={"code": "OPCANCEL", "name": "Lavage opérateur", "price": 3000}).json()
    ticket = client.post("/api/v1/tickets", headers=headers, json={
        "station_id": station["id"], "vehicle_type": "SUV",
        "lines": [{"service_id": service["id"], "quantity": 1}],
    }).json()
    response = client.post(f"/api/v1/tickets/{ticket['id']}/cancel",
        headers=operator_headers, json={"reason": "Annulation demandée"})
    assert response.status_code == 403
