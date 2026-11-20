from app.models import CashSession, CashMovement
def test_cash_session_open_move_and_close(client):
    from tests.test_tickets_api import create_owner_and_login
    token, station_id = create_owner_and_login(client)
    headers={"Authorization":f"Bearer {token}"}
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
