def _expense_owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_expense_partial_and_full_payments(client):
    headers=_expense_owner(client,"expenseowner@example.com","EXP1")
    station=client.get("/api/v1/stations",headers=headers).json()[0]["id"]
    created=client.post("/api/v1/expenses",headers=headers,json={"station_id":station,"category":"produits_lavage",
      "label":"Achat shampoing","vendor":"Fournisseur A","expense_date":"2026-11-20","amount":25000})
    assert created.status_code==201,created.text
    expense=created.json()
    assert expense["status"]=="unpaid" and expense["remaining_amount"]==25000
    first=client.post(f"/api/v1/expenses/{expense['id']}/payments",headers=headers,json={"amount":10000,"method":"cash"})
    assert first.status_code==201,first.text
    assert first.json()["status"]=="partial" and first.json()["remaining_amount"]==15000
    over=client.post(f"/api/v1/expenses/{expense['id']}/payments",headers=headers,json={"amount":16000,"method":"wave"})
    assert over.status_code==422
    last=client.post(f"/api/v1/expenses/{expense['id']}/payments",headers=headers,json={"amount":15000,"method":"wave","reference":"TX-123"})
    assert last.status_code==201,last.text
    assert last.json()["status"]=="paid" and last.json()["remaining_amount"]==0
    summary=client.get("/api/v1/expenses/summary",headers=headers).json()
    assert summary["committed_amount"]==25000 and summary["paid_amount"]==25000

def test_expenses_are_isolated_between_companies(client):
    a=_expense_owner(client,"expensea@example.com","EXA1")
    b=_expense_owner(client,"expenseb@example.com","EXB1")
    station=client.get("/api/v1/stations",headers=a).json()[0]["id"]
    created=client.post("/api/v1/expenses",headers=a,json={"station_id":station,"category":"eau",
      "label":"Facture eau","expense_date":"2026-11-20","amount":12000})
    assert created.status_code==201
    assert client.get("/api/v1/expenses",headers=b).json()==[]
    assert client.get(f"/api/v1/expenses/{created.json()['id']}",headers=b).status_code==404
    assert client.post(f"/api/v1/expenses/{created.json()['id']}/payments",headers=b,json={"amount":1000,"method":"cash"}).status_code==404
