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


def test_overview_includes_coverage_and_dates(client):
    """overview 新增字段：首尾日期、大洲数、地球覆盖率。"""
    resp = client.get("/api/stats/overview")
    data = resp.get_json()
    assert data["first_trip_date"] == "2019-04-27", "first_trip_date 应为最早的 start_date"
    assert data["last_trip_date"] == "2019-10-01"
    assert data["total_continents"] == 1, "缅甸和日本都在亚洲"
    # 2 国 / 195 ≈ 1.0
    assert data["world_coverage"] == round(2 / 195 * 100, 1)


def test_destinations_by_continent(client):
    """destinations 新增按大洲聚合。"""
    resp = client.get("/api/stats/destinations")
    data = resp.get_json()
    assert "by_continent" in data
    asia = next((c for c in data["by_continent"] if c["continent"] == "亚洲"), None)
    assert asia is not None, "应包含亚洲"
    assert asia["country_count"] == 2, "缅甸 + 日本"
    assert asia["trip_count"] == 2
    assert "缅甸" in asia["countries"]
    assert "日本" in asia["countries"]


def test_expenses_by_country(client):
    """expenses 新增按国家归属聚合（按 trip 主要国家）。"""
    resp = client.get("/api/stats/expenses")
    data = resp.get_json()
    assert "by_country" in data
    country_dict = {item["country"]: item["total"] for item in data["by_country"]}
    assert country_dict["缅甸"] == round(3344 + 1346.52, 2)
    assert country_dict["日本"] == round(5000 + 8000, 2)


def test_highlights_endpoint(client):
    """highlights 返回六项之最，叶子字段可用。"""
    resp = client.get("/api/stats/highlights")
    data = resp.get_json()

    assert data["earliest"]["title"] == "Japan Trip"
    assert data["earliest"]["value"] == "2019-04-27"

    # 日本 2019-04-27 ~ 2019-05-04 = 7 天，缅甸 2019-10-01 ~ 2019-10-07 = 6 天
    assert data["longest"]["title"] == "Japan Trip"
    assert data["longest"]["value"] == "7 天"

    assert data["most_expensive"]["title"] == "Japan Trip"
    assert "¥13,000" in data["most_expensive"]["value"]

    assert data["cheapest_per_day"] is not None
    assert data["cheapest_per_day"]["title"] == "Myanmar Trip"

    # 无评分时 rated 返回 None
    assert data["highest_rated"] is None
    assert data["lowest_rated"] is None


def test_highlights_empty_safe():
    """无旅行时 highlights 应安全返回全 None。"""
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/api/stats/highlights")
        data = resp.get_json()
        for k in ["earliest", "longest", "most_expensive",
                  "cheapest_per_day", "highest_rated", "lowest_rated"]:
            assert data[k] is None, f"{k} 在无数据时应为 None"


def test_timeline_by_month_and_companion(client):
    """timeline 返回月份分布和旅伴类型。"""
    resp = client.get("/api/stats/timeline")
    data = resp.get_json()

    months = {item["month"]: item["trip_count"] for item in data["by_month"]}
    assert len(months) == 12, "必须 12 个月都在"
    assert months[4] == 1, "日本 4 月出发"
    assert months[10] == 1, "缅甸 10 月出发"
    assert months[1] == 0

    companion = {item["type"]: item["count"] for item in data["by_companion"]}
    assert companion["结伴"] == 2, "两次旅行 traveler_count=2 都是结伴"
    assert companion["独行"] == 0
    assert companion["家庭/多人"] == 0
