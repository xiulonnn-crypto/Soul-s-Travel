import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


SAMPLE_TRIP = {
    "title": "Test Trip",
    "start_date": "2024-01-01",
    "end_date": "2024-01-05",
    "traveler_count": 2,
    "status": "completed",
    "legs": [{
        "order_index": 1,
        "city": "Tokyo",
        "country": "Japan",
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "days": [{
            "day_number": 1,
            "date": "2024-01-01",
            "description": "Arrival",
            "activities": ["Shibuya"],
            "transport": ["Flight"],
            "accommodation": "Hotel A"
        }]
    }],
    "expenses": [{
        "category": "交通",
        "amount": 5000,
        "currency": "CNY",
        "description": "Flight",
        "date": "2024-01-01"
    }]
}


def test_create_and_get_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Test Trip"
    assert len(data["legs"]) == 1
    assert len(data["expenses"]) == 1

    resp2 = client.get(f"/api/trips/{data['id']}")
    assert resp2.status_code == 200
    assert resp2.get_json()["legs"][0]["days"][0]["activities"] == ["Shibuya"]


def test_list_trips(client):
    client.post("/api/trips", json=SAMPLE_TRIP)
    resp = client.get("/api/trips")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_list_trips_filter_status(client):
    client.post("/api/trips", json=SAMPLE_TRIP)
    resp = client.get("/api/trips?status=planned")
    assert len(resp.get_json()) == 0
    resp2 = client.get("/api/trips?status=completed")
    assert len(resp2.get_json()) == 1


def test_update_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]
    resp2 = client.put(f"/api/trips/{trip_id}", json={"title": "Updated"})
    assert resp2.status_code == 200
    assert resp2.get_json()["title"] == "Updated"


def test_delete_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]
    resp2 = client.delete(f"/api/trips/{trip_id}")
    assert resp2.status_code == 200
    resp3 = client.get(f"/api/trips/{trip_id}")
    assert resp3.status_code == 404


def test_get_nonexistent_trip(client):
    resp = client.get("/api/trips/999")
    assert resp.status_code == 404
