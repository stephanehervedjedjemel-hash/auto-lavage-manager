def _owner(client,email,code):
    response=client.post("/api/v1/auth/register-owner",json={"bootstrap_secret":"CHANGE_ME_BOOTSTRAP_SECRET",
      "company_legal_name":"Société "+code,"company_display_name":"Lavage "+code,
      "station_name":"Station "+code,"station_code":code,"owner_full_name":"Admin "+code,
      "owner_email":email,"password":"MotDePasseTresSolide123"})
    assert response.status_code==201,response.text
    return {"Authorization":"Bearer "+response.json()["access_token"]}


def test_financial_report_exports_pdf_and_xlsx(client):
    headers=_owner(client,"exportowner@example.com","EXP1")
    for file_format,content_type,signature in [
        ("pdf","application/pdf",b"%PDF"),("xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",b"PK")
    ]:
        response=client.get(f"/api/v1/reports/financial/export?format={file_format}&period=custom&start_date=2026-11-20&end_date=2026-11-20",headers=headers)
        assert response.status_code==200,response.text
        assert response.headers["content-type"].startswith(content_type)
        assert response.content.startswith(signature)
        assert "attachment;" in response.headers["content-disposition"]


def test_financial_report_export_rejects_unknown_station(client):
    owner_a=_owner(client,"exporta@example.com","EXPA")
    owner_b=_owner(client,"exportb@example.com","EXPB")
    station_a=client.get("/api/v1/stations",headers=owner_a).json()[0]["id"]
    response=client.get(f"/api/v1/reports/financial/export?format=xlsx&station_id={station_a}",headers=owner_b)
    assert response.status_code==404
