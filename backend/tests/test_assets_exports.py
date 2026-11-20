from io import BytesIO
from openpyxl import load_workbook


def _owner(client,email,code):
    response=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert response.status_code==201,response.text
    return {"Authorization":"Bearer "+response.json()["access_token"]}


def test_asset_register_exports_pdf_and_xlsx_with_depreciation(client):
    headers=_owner(client,"assetexport@example.com","AEX1")
    station=client.get("/api/v1/stations",headers=headers).json()[0]["id"]
    created=client.post("/api/v1/assets",headers=headers,json={
        "station_id":station,"asset_code":"POMPE-EXPORT","name":"Pompe haute pression",
        "category":"equipement","acquisition_date":"2026-01-10","in_service_date":"2026-02-01",
        "acquisition_cost":1200000,"residual_value":0,"useful_life_months":60
    })
    assert created.status_code==201,created.text
    for fmt,content_type,signature in [
        ("pdf","application/pdf",b"%PDF"),
        ("xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",b"PK"),
    ]:
        response=client.get(f"/api/v1/assets/export?format={fmt}&as_of=2026-04-30",headers=headers)
        assert response.status_code==200,response.text
        assert response.headers["content-type"].startswith(content_type)
        assert response.content.startswith(signature)
        assert "attachment;" in response.headers["content-disposition"]
        if fmt=="xlsx":
            workbook=load_workbook(BytesIO(response.content),read_only=True)
            sheet=workbook["Immobilisations"]
            values=list(sheet.values)
            assert values[1][0]=="POMPE-EXPORT"
            assert values[1][12]==60000
            assert values[1][13]==1140000


def test_asset_export_cannot_read_another_company_station(client):
    owner_a=_owner(client,"assetexporta@example.com","AEXA")
    owner_b=_owner(client,"assetexportb@example.com","AEXB")
    station_a=client.get("/api/v1/stations",headers=owner_a).json()[0]["id"]
    response=client.get(f"/api/v1/assets/export?format=xlsx&station_id={station_a}",headers=owner_b)
    assert response.status_code==404
