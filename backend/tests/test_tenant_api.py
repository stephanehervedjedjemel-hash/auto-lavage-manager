def register(client,owner,company,station):
    response=client.post("/api/v1/auth/register-owner",json={
      "bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":company+" SARL","company_display_name":company,
      "company_email":owner,"station_name":station,"station_code":"MAIN",
      "owner_full_name":"Admin "+company,"owner_email":owner,
      "password":"MotDePasse-Securise-2026"})
    assert response.status_code==201,response.text
    return response.json()
def auth(client,email):
    response=client.post("/api/v1/auth/login",json={"email":email,"password":"MotDePasse-Securise-2026"})
    assert response.status_code==200,response.text
    return {"Authorization":"Bearer "+response.json()["access_token"]}
def test_tenants_only_see_their_own_stations(client):
    first=register(client,"admin1@example.com","Lavage Alpha","Alpha Centre")
    register(client,"admin2@example.com","Lavage Beta","Beta Centre")
    h1=auth(client,"admin1@example.com")
    h2=auth(client,"admin2@example.com")
    stations1=client.get("/api/v1/stations",headers=h1).json()
    stations2=client.get("/api/v1/stations",headers=h2).json()
    assert len(stations1)==1 and stations1[0]["name"]=="Alpha Centre"
    assert len(stations2)==1 and stations2[0]["name"]=="Beta Centre"
    assert stations1[0]["company_id"]!=stations2[0]["company_id"]
def test_admin_can_create_user_for_own_station(client):
    register(client,"admin@example.com","Lavage Gamma","Gamma Centre")
    headers=auth(client,"admin@example.com")
    station=client.get("/api/v1/stations",headers=headers).json()[0]
    response=client.post("/api/v1/users",headers=headers,json={
      "full_name":"Agent Test","email":"agent@example.com","password":"Autre-MotDePasse-2026",
      "role":"operator","station_id":station["id"]})
    assert response.status_code==201,response.text
    assert response.json()["station_id"]==station["id"]
def test_admin_cannot_assign_user_to_another_tenant_station(client):
    register(client,"owner-a@example.com","Lavage A","Station A")
    register(client,"owner-b@example.com","Lavage B","Station B")
    headers=auth(client,"owner-a@example.com")
    station_b=client.get("/api/v1/stations",headers=auth(client,"owner-b@example.com")).json()[0]
    response=client.post("/api/v1/users",headers=headers,json={
      "full_name":"Agent Intrus","email":"intrus@example.com","password":"MotDePasse-Long-2026",
      "role":"operator","station_id":station_b["id"]})
    assert response.status_code==404
