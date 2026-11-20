def _owner(client,email,code):
    r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,
      "station_code":code,"owner_full_name":"Admin","owner_email":email,"password":"MotDePasseTresSolide123"})
    assert r.status_code==201,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_supplier_specific_prices_and_historical_purchase_cost(client):
    h=_owner(client,"stock@example.com","STK1")
    station=client.get("/api/v1/stations",headers=h).json()[0]["id"]
    s1=client.post("/api/v1/suppliers",headers=h,json={"name":"Fournisseur A"}).json()
    s2=client.post("/api/v1/suppliers",headers=h,json={"name":"Fournisseur B"}).json()
    p=client.post("/api/v1/inventory/products",headers=h,json={"sku":"SHAMP-1","name":"Shampooing","category":"lavage","unit":"litre","minimum_stock":5}).json()
    assert client.put(f"/api/v1/inventory/products/{p['id']}/suppliers/{s1['id']}/price",headers=h,json={"purchase_price":1200}).json()["purchase_price"]==1200
    client.put(f"/api/v1/inventory/products/{p['id']}/suppliers/{s2['id']}/price",headers=h,json={"purchase_price":1500})
    purchase=client.post("/api/v1/inventory/movements",headers=h,json={"station_id":station,"product_id":p["id"],"supplier_id":s1["id"],"movement_type":"in","quantity":10,"unit_cost":1200,"reference":"FACT-001"})
    assert purchase.status_code==201 and purchase.json()["stock_after"]==10
    # A subsequent supplier price update must not rewrite the saved movement cost.
    client.put(f"/api/v1/inventory/products/{p['id']}/suppliers/{s1['id']}/price",headers=h,json={"purchase_price":1350})
    movements=client.get("/api/v1/inventory/movements",headers=h).json()
    assert movements[0]["unit_cost"]==1200 and movements[0]["supplier_id"]==s1["id"]
    out=client.post("/api/v1/inventory/movements",headers=h,json={"station_id":station,"product_id":p["id"],"movement_type":"out","quantity":3})
    assert out.status_code==201 and out.json()["stock_after"]==7
    assert client.post("/api/v1/inventory/movements",headers=h,json={"station_id":station,"product_id":p["id"],"movement_type":"out","quantity":8}).status_code==422

def test_inventory_tenant_isolation(client):
    a=_owner(client,"stock-a@example.com","STA1");b=_owner(client,"stock-b@example.com","STB1")
    p=client.post("/api/v1/inventory/products",headers=a,json={"sku":"PRIVATE","name":"Produit privé","category":"chimie"}).json()
    assert client.get("/api/v1/inventory/products",headers=b).json()==[]
    assert client.put(f"/api/v1/inventory/products/{p['id']}/suppliers/999/price",headers=b,json={"purchase_price":10}).status_code==404
