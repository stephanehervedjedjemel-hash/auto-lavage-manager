def _cash_owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}
def test_cash_session_open_move_and_close(client):
    headers=_cash_owner(client,"cashowner@example.com","CSH1")
    station_id=client.get("/api/v1/stations",headers=headers).json()[0]["id"]
    opened=client.post("/api/v1/cash/sessions",headers=headers,json={"station_id":station_id,"opening_amount":10000})
    assert opened.status_code==201,opened.text
    sid=opened.json()["id"]
    duplicate=client.post("/api/v1/cash/sessions",headers=headers,json={"station_id":station_id,"opening_amount":0})
    assert duplicate.status_code==409
    movement=client.post(f"/api/v1/cash/sessions/{sid}/movements",headers=headers,json={"direction":"out","amount":1500,"reason":"Achat fournitures"})
    assert movement.status_code==201,movement.text
    closed=client.post(f"/api/v1/cash/sessions/{sid}/close",headers=headers,json={"closing_amount":8500})
    assert closed.status_code==200,closed.text
    assert closed.json()["expected_amount"]==8500
    assert closed.json()["difference"]==0
