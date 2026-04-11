import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine

TRIP = {
    "title": "Share Test", "start_date": "2024-01-01", "end_date": "2024-01-03",
    "status": "completed", "legs": [], "expenses": [],
}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_share_flow(client):
    resp = client.post("/api/trips", json=TRIP)
    trip_id = resp.get_json()["id"]

    resp2 = client.post(f"/api/trips/{trip_id}/share")
    token = resp2.get_json()["share_token"]
    assert len(token) == 12

    resp3 = client.get(f"/api/share/{token}")
    assert resp3.status_code == 200
    assert resp3.get_json()["title"] == "Share Test"

    client.delete(f"/api/trips/{trip_id}/share")
    resp4 = client.get(f"/api/share/{token}")
    assert resp4.status_code == 404
