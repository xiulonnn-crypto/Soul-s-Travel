import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app

TRIP_MYANMAR = {
    "title": "Myanmar Trip", "start_date": "2019-10-01", "end_date": "2019-10-07",
    "traveler_count": 2, "status": "completed",
    "legs": [
        {"order_index": 1, "city": "Mandalay", "country": "缅甸",
         "start_date": "2019-10-01", "end_date": "2019-10-03", "days": []},
        {"order_index": 2, "city": "Bagan", "country": "缅甸",
         "start_date": "2019-10-03", "end_date": "2019-10-05", "days": []},
        {"order_index": 3, "city": "Inle", "country": "缅甸",
         "start_date": "2019-10-05", "end_date": "2019-10-07", "days": []},
    ],
    "expenses": [{"category": "交通", "amount": 3344, "date": "2019-10-01"},
                 {"category": "住宿", "amount": 1346.52, "date": "2019-10-01"}],
}

TRIP_JAPAN = {
    "title": "Japan Trip", "start_date": "2019-04-27", "end_date": "2019-05-04",
    "traveler_count": 2, "status": "completed",
    "legs": [
        {"order_index": 1, "city": "东京", "country": "日本",
         "start_date": "2019-04-27", "end_date": "2019-04-30", "days": []},
        {"order_index": 2, "city": "奈良", "country": "[待确认]",
         "start_date": "2019-04-30", "end_date": "2019-05-02", "days": []},
        {"order_index": 3, "city": "大阪", "country": "日本",
         "start_date": "2019-05-02", "end_date": "2019-05-04", "days": []},
    ],
    "expenses": [{"category": "交通", "amount": 5000, "date": "2019-04-27"},
                 {"category": "住宿", "amount": 8000, "date": "2019-04-27"}],
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/api/trips", json=TRIP_MYANMAR)
        c.post("/api/trips", json=TRIP_JAPAN)
        yield c


def test_overview(client):
    resp = client.get("/api/stats/overview")
    data = resp.get_json()
    assert data["total_trips"] == 2
    assert data["total_countries"] == 2, "should exclude [待确认]"


def test_destinations_country_count_per_trip(client):
    """Country visits should count per-trip, not per-leg; exclude [待确认]."""
    resp = client.get("/api/stats/destinations")
    data = resp.get_json()
    country_dict = dict(data["countries"])
    assert "[待确认]" not in country_dict, "[待确认] should be filtered"
    assert country_dict["缅甸"] == 1, "3 legs in same country = 1 visit"
    assert country_dict["日本"] == 1, "multiple legs same country = 1 visit"


def test_destinations_city_excludes_pending(client):
    """Cities with [待确认] country should still show, but [待确认] cities should not."""
    resp = client.get("/api/stats/destinations")
    data = resp.get_json()
    city_dict = dict(data["cities"])
    assert "Mandalay" in city_dict
    assert "东京" in city_dict


def test_expense_stats(client):
    resp = client.get("/api/stats/expenses")
    data = resp.get_json()
    assert len(data["by_category"]) == 2
    assert len(data["by_trip"]) == 2


def test_expense_by_year(client):
    """New endpoint: expenses grouped by year."""
    resp = client.get("/api/stats/expenses")
    data = resp.get_json()
    assert "by_year" in data, "should include by_year field"
    year_dict = {item["year"]: item["total"] for item in data["by_year"]}
    assert 2019 in year_dict
