from app import app


def test_health():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "UP"


def test_home():
    client = app.test_client()
    resp = client.get("/")
    assert b"DevOps Demo" in resp.data
