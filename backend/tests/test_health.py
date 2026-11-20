from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health_endpoint():
    response=client.get("/health")
    assert response.status_code==200 and response.json()["status"]=="ok"
def test_api_root_defaults_to_xof_and_french():
    data=client.get("/api/v1").json()
    assert data["currency"]=="XOF" and data["language"]=="fr"
def test_station_list_requires_authentication():
    assert client.get("/api/v1/stations").status_code==401
