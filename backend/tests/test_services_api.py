def _create_company(client,email,code):
    response=client.post("/api/v1/auth/register-owner",json={
        "bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
        "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
        "station_name":"Station principale","station_code":code,
        "owner_full_name":"Administrateur "+code,"owner_email":email,
        "password":"MotDePasseTresSolide123"
    })
    assert response.status_code==201,response.text
    return {"Authorization":"Bearer "+response.json()["access_token"]}
def test_service_catalog_is_company_isolated(client):
    h1=_create_company(client,"owner1@example.com","ST1")
    h2=_create_company(client,"owner2@example.com","ST2")
    created=client.post("/api/v1/services",headers=h1,json={
        "code":"LAVAGE_EXT","name":"Lavage extérieur","price":3000,"duration_minutes":25
    })
    assert created.status_code==201,created.text
    assert client.get("/api/v1/services",headers=h1).json()[0]["name"]=="Lavage extérieur"
    assert client.get("/api/v1/services",headers=h2).json()==[]
    assert client.patch(f"/api/v1/services/{created.json()['id']}",headers=h2,json={"price":1}).status_code==404
def test_service_station_scope_and_validation(client):
    headers=_create_company(client,"owner3@example.com","ST3")
    station=client.post("/api/v1/stations",headers=headers,json={"name":"Deuxième station","code":"ST3B"}).json()
    bad=client.post("/api/v1/services",headers=headers,json={
        "code":"BAD","name":"Service hors tenant","price":1000,"station_id":99999
    })
    assert bad.status_code==404
    response=client.post("/api/v1/services",headers=headers,json={
        "code":"LAVAGE_INT","name":"Lavage intérieur","price":2500,"station_id":station["id"]
    })
    assert response.status_code==201,response.text
    assert response.json()["station_id"]==station["id"]
    assert client.post("/api/v1/services",headers=headers,json={
        "code":"ZERO","name":"Prix invalide","price":-10
    }).status_code==422
