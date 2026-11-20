def _asset_owner(client,email,code):
 r=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET","company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,"station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,"owner_email":email,"password":"MotDePasseTresSolide123"})
 assert r.status_code==201,r.text
 return {"Authorization":"Bearer "+r.json()["access_token"]}
def test_asset_straight_line_depreciation_and_summary(client):
 h=_asset_owner(client,"assetowner@example.com","AST1"); st=client.get("/api/v1/stations",headers=h).json()[0]["id"]
 r=client.post("/api/v1/assets",headers=h,json={"station_id":st,"asset_code":"NETTOYEUR-001","name":"Nettoyeur haute pression","category":"materiel_lavage","acquisition_date":"2026-01-10","in_service_date":"2026-02-01","acquisition_cost":1200000,"residual_value":0,"useful_life_months":60})
 assert r.status_code==201,r.text
 a=client.get("/api/v1/assets?as_of=2026-04-30",headers=h).json()[0]
 assert (a["depreciation_months"],a["monthly_depreciation"],a["accumulated_depreciation"],a["net_book_value"])==(3,20000,60000,1140000)
 s=client.get("/api/v1/assets/summary?as_of=2026-04-30",headers=h).json()
 assert s["acquisition_cost_total"]==1200000 and s["accumulated_depreciation_total"]==60000 and s["net_book_value_total"]==1140000
def test_asset_validation_and_tenant_isolation(client):
 a=_asset_owner(client,"asset-a@example.com","ASA1"); b=_asset_owner(client,"asset-b@example.com","ASB1")
 st=client.get("/api/v1/stations",headers=a).json()[0]["id"]
 bad=client.post("/api/v1/assets",headers=a,json={"station_id":st,"asset_code":"BAD","name":"Pompe","category":"equipement","acquisition_date":"2026-04-01","in_service_date":"2026-03-01","acquisition_cost":100000,"residual_value":120000,"useful_life_months":12})
 assert bad.status_code==422
 good=client.post("/api/v1/assets",headers=a,json={"station_id":st,"asset_code":"POMPE-1","name":"Pompe","category":"equipement","acquisition_date":"2026-01-01","in_service_date":"2026-01-01","acquisition_cost":600000,"useful_life_months":24})
 assert good.status_code==201
 assert client.get("/api/v1/assets",headers=b).json()==[]
 assert client.get("/api/v1/assets/summary",headers=b).json()["assets_count"]==0
