import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import get_session
from models import TripEvaluation
import json


@pytest.fixture
def client():
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


def test_update_trip_invalidates_evaluation_cache(client):
    """修改行程后旧 evaluation 缓存必须失效，避免遗漏景点等基于过期 leg/day 数据。"""
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]

    session = get_session()
    session.add(TripEvaluation(
        trip_id=trip_id,
        overall_score=85,
        evaluation_data=json.dumps({"summary": "stale"}),
    ))
    session.commit()
    session.close()

    resp2 = client.put(f"/api/trips/{trip_id}", json={"title": "Changed"})
    assert resp2.status_code == 200

    session = get_session()
    remaining = session.query(TripEvaluation).filter_by(trip_id=trip_id).count()
    session.close()
    assert remaining == 0, (
        f"Expected stale evaluation cache to be cleared on PUT, found {remaining}"
    )


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


def test_list_trips_includes_evaluation_score(client):
    """行程列表 API 应在已有评价时返回 evaluation_score 字段。"""
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]

    # 直接写入一条评价记录
    session = get_session()
    ev = TripEvaluation(
        trip_id=trip_id,
        overall_score=85,
        evaluation_data=json.dumps({"summary": "excellent"}),
    )
    session.add(ev)
    session.commit()
    session.close()

    resp2 = client.get("/api/trips")
    trips = resp2.get_json()
    assert len(trips) == 1
    assert trips[0]["evaluation_score"] == 85


def test_list_trips_evaluation_score_none_when_no_evaluation(client):
    """未评价的行程，evaluation_score 应为 None。"""
    client.post("/api/trips", json=SAMPLE_TRIP)
    resp = client.get("/api/trips")
    trips = resp.get_json()
    assert trips[0]["evaluation_score"] is None


def test_create_trip_with_null_dates(client):
    """Bug: fromisoformat: argument must be str — when AI parser outputs None dates."""
    payload = {
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
                "date": None,
                "description": "Arrival",
                "activities": ["Shibuya"],
                "transport": [],
                "accommodation": "Hotel A"
            }]
        }],
        "expenses": [{
            "category": "交通",
            "amount": 5000,
            "currency": "CNY",
            "description": "Flight",
            "date": None
        }]
    }
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Test Trip"
    assert data["legs"][0]["days"][0]["date"] == "2024-01-01"
    assert data["expenses"][0]["date"] == "2024-01-01"


MULTI_LEG_TRIP = {
    "title": "韩国之旅",
    "start_date": "2023-09-01",
    "end_date": "2023-09-10",
    "traveler_count": 2,
    "status": "completed",
    "legs": [
        {
            "order_index": 1,
            "city": "首尔",
            "country": "韩国",
            "start_date": "2023-09-01",
            "end_date": "2023-09-05",
            "days": [{
                "day_number": 1,
                "date": "2023-09-01",
                "activities": ["景福宫"],
                "transport": [],
                "accommodation": "Hotel Seoul",
            }],
        },
        {
            "order_index": 2,
            "city": "济州岛",
            "country": "韩国",
            "start_date": "2023-09-05",
            "end_date": "2023-09-10",
            "days": [{
                "day_number": 1,
                "date": "2023-09-05",
                "activities": ["汉拿山"],
                "transport": [],
                "accommodation": "Hotel Jeju",
            }],
        },
    ],
    "expenses": [],
}


def test_visited_destinations_new_format(client):
    """同一行程多个 leg 应在 profile 中合并为数组格式的单条记录。"""
    client.post("/api/trips", json=MULTI_LEG_TRIP)

    resp = client.get("/api/profile")
    assert resp.status_code == 200
    visited = resp.get_json()["visited_countries_cities"]

    # 新格式：{country: [{date, cities}]}
    assert "韩国" in visited
    korea = visited["韩国"]
    assert isinstance(korea, list), f"期望 list，实际是 {type(korea)}"
    assert len(korea) == 1
    entry = korea[0]
    assert entry["date"] == "2023-09"          # Trip.start_date 所在年月
    assert "首尔" in entry["cities"]
    assert "济州岛" in entry["cities"]


def test_profile_get_migrates_old_format(client):
    """profile GET 遇到旧格式数据（dict of dicts）时应自动迁移，不崩溃。"""
    from database import get_session
    from models import UserProfile
    import json

    # 先创建实际行程（迁移时需要从 trips 重新生成）
    client.post("/api/trips", json=MULTI_LEG_TRIP)

    # 将 visited_countries_cities 手动覆写为旧格式
    session = get_session()
    profile = session.query(UserProfile).first()
    profile.visited_countries_cities = json.dumps(
        {"韩国": {"首尔": "2023-09", "济州岛": "2023-09"}},
        ensure_ascii=False,
    )
    session.commit()
    session.close()

    # GET 不应崩溃，且应返回新格式（从 trips 重新生成）
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    visited = resp.get_json()["visited_countries_cities"]
    assert "韩国" in visited
    assert isinstance(visited["韩国"], list), "旧格式应已迁移为 list"
    assert any("首尔" in e["cities"] for e in visited["韩国"])
