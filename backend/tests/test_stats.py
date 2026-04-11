import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine

TRIP = {
    "title": "Myanmar", "start_date": "2019-10-01", "end_date": "2019-10-07",
    "traveler_count": 2, "status": "completed",
    "legs": [{"order_index": 1, "city": "Mandalay", "country": "Myanmar",
              "start_date": "2019-10-01", "end_date": "2019-10-03", "days": []}],
    "expenses": [{"category": "交通", "amount": 3344, "date": "2019-10-01"},
                 {"category": "住宿", "amount": 1346.52, "date": "2019-10-01"}],
}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/api/trips", json=TRIP)
        yield c


def test_overview(client):
    resp = client.get("/api/stats/overview")
    data = resp.get_json()
    assert data["total_trips"] == 1
    assert data["total_countries"] == 1
    assert data["total_expense"] == 4690.52


def test_destinations(client):
    resp = client.get("/api/stats/destinations")
    data = resp.get_json()
    assert data["countries"][0][0] == "Myanmar"


def test_expense_stats(client):
    resp = client.get("/api/stats/expenses")
    data = resp.get_json()
    assert len(data["by_category"]) == 2
    assert len(data["by_trip"]) == 1
