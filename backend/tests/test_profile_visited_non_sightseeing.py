"""routes.trips._sync_visited_destinations 写入 UserProfile.visited_countries_cities
应排除「无任何游览证据的 leg」(返程终点 / 中转 / 起讫点),与卡片 destination_label
的判定保持一致。

复现 bug：肯尼亚行程的「北京返程 leg」(activities=[]、accommodation 空、含跨境
航班) 被错误聚合为「中国 → 北京」出现在个人档案的「去过的地方」里;同样地,
英国行程的「文莱 5h 中转 leg」也被聚合为「文莱 → 斯里巴加湾市」。

修复后：_sync_visited_destinations 应复用 services.evaluator._is_non_sightseeing_leg
判定,把这类 leg 从 visited_countries_cities 中过滤掉,与 Trip.to_dict(include_summary=True)
里 destination_label 的语义保持一致(对称守卫)。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Trip, Leg, TripDay, UserProfile
from routes.trips import _sync_visited_destinations


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()


def _add_leg(session, trip, order, city, country, sd, ed, days):
    leg = Leg(trip=trip, order_index=order, city=city, country=country,
              start_date=sd, end_date=ed)
    session.add(leg)
    for j, day in enumerate(days):
        session.add(TripDay(
            leg=leg, day_number=j + 1, date=sd,
            activities=json.dumps(day.get("activities", []), ensure_ascii=False),
            transport=json.dumps(day.get("transport", []), ensure_ascii=False),
            accommodation=day.get("accommodation"),
        ))


def _build_kenya_trip_with_return_home(session):
    """肯尼亚 4 个游览 leg + 北京返程 leg(无 activities、无 accommodation)。"""
    trip = Trip(title="kenya-trip", start_date=date(2025, 5, 1),
                end_date=date(2025, 5, 11), status="completed")
    session.add(trip)
    _add_leg(session, trip, 0, "内罗毕", "肯尼亚", date(2025, 5, 1), date(2025, 5, 3),
             [{"activities": ["国家博物馆"], "accommodation": "Hotel Nairobi", "transport": []}])
    _add_leg(session, trip, 1, "马赛马拉国家保护区", "肯尼亚", date(2025, 5, 3), date(2025, 5, 7),
             [{"activities": ["大草原 Safari"], "accommodation": "Mara Camp", "transport": []}])
    _add_leg(session, trip, 2, "纳库鲁", "肯尼亚", date(2025, 5, 7), date(2025, 5, 9),
             [{"activities": ["纳库鲁湖国家公园"], "accommodation": "Hotel Nakuru", "transport": []}])
    _add_leg(session, trip, 3, "奈瓦沙", "肯尼亚", date(2025, 5, 9), date(2025, 5, 10),
             [{"activities": ["奈瓦沙湖"], "accommodation": "Hotel Naivasha", "transport": []}])
    _add_leg(session, trip, 4, "北京", "中国", date(2025, 5, 11), date(2025, 5, 11),
             [{"activities": [], "accommodation": "",
               "transport": ["哈马德国际机场 01:45-北京大兴国际机场 14:40"]}])
    session.commit()
    return trip


def _build_uk_trip_with_transit_and_return_home(session):
    """文莱中转 leg + 伦敦 + 爱丁堡 + 北京返程 leg。"""
    trip = Trip(title="uk-trip", start_date=date(2024, 9, 28),
                end_date=date(2024, 10, 8), status="completed")
    session.add(trip)
    _add_leg(session, trip, 0, "斯里巴加湾市", "文莱", date(2024, 9, 28), date(2024, 9, 28),
             [{"activities": [], "accommodation": "",
               "transport": ["北京-斯里巴加湾市 转机"]}])
    _add_leg(session, trip, 1, "伦敦", "英国", date(2024, 9, 29), date(2024, 10, 3),
             [{"activities": ["大英博物馆"], "accommodation": "Hotel London",
               "transport": ["BN-LON"]}])
    _add_leg(session, trip, 2, "爱丁堡", "英国", date(2024, 10, 3), date(2024, 10, 7),
             [{"activities": ["爱丁堡城堡"], "accommodation": "Hotel Edinburgh",
               "transport": ["LON-EDI"]}])
    _add_leg(session, trip, 3, "北京", "中国", date(2024, 10, 8), date(2024, 10, 8),
             [{"activities": [], "accommodation": "",
               "transport": ["伦敦-北京"]}])
    session.commit()
    return trip


def _build_thailand_trip_all_sightseeing(session):
    """对照组:纯游览 3 leg,无任何 non-sightseeing leg。"""
    trip = Trip(title="thai-trip", start_date=date(2024, 9, 15),
                end_date=date(2024, 9, 22), status="completed")
    session.add(trip)
    _add_leg(session, trip, 0, "曼谷", "泰国", date(2024, 9, 15), date(2024, 9, 18),
             [{"activities": ["大皇宫"], "accommodation": "Hotel BKK", "transport": []}])
    _add_leg(session, trip, 1, "清迈", "泰国", date(2024, 9, 18), date(2024, 9, 20),
             [{"activities": ["双龙寺"], "accommodation": "Hotel CNX", "transport": []}])
    _add_leg(session, trip, 2, "清莱", "泰国", date(2024, 9, 20), date(2024, 9, 22),
             [{"activities": ["白庙"], "accommodation": "Hotel CEI", "transport": []}])
    session.commit()
    return trip


def _visited(session):
    profile = session.query(UserProfile).first()
    return json.loads(profile.visited_countries_cities) if profile and profile.visited_countries_cities else {}


class TestSyncVisitedExcludesNonSightseeing:
    """visited_countries_cities 应排除返程终点 / 纯中转的非游览 leg。"""

    def test_kenya_trip_excludes_beijing_return_home(self, session):
        """肯尼亚 4 个 leg + 北京返程 → visited 只有肯尼亚的 4 个城市,无 '中国' 键。"""
        _build_kenya_trip_with_return_home(session)
        _sync_visited_destinations(session)
        v = _visited(session)
        assert "中国" not in v, (
            f"期望返程北京被排除,得到 visited={v!r}"
        )
        assert v.get("肯尼亚") and v["肯尼亚"][0]["cities"] == [
            "内罗毕", "马赛马拉国家保护区", "纳库鲁", "奈瓦沙"
        ], f"肯尼亚 4 个游览 leg 应完整保留,得到 {v.get('肯尼亚')!r}"

    def test_uk_trip_excludes_brunei_transit_and_beijing_return(self, session):
        """文莱 5h 中转 + 英国 + 北京返程 → visited 只含 '英国' 的 2 个城市。"""
        _build_uk_trip_with_transit_and_return_home(session)
        _sync_visited_destinations(session)
        v = _visited(session)
        assert "中国" not in v, f"期望返程北京被排除,得到 visited={v!r}"
        assert "文莱" not in v, f"期望中转文莱被排除,得到 visited={v!r}"
        assert v.get("英国") and v["英国"][0]["cities"] == ["伦敦", "爱丁堡"], (
            f"英国 2 个游览 leg 应完整保留,得到 {v.get('英国')!r}"
        )

    def test_thailand_trip_unchanged_when_no_transit(self, session):
        """对照组:纯游览 trip 应完整保留所有 leg。"""
        _build_thailand_trip_all_sightseeing(session)
        _sync_visited_destinations(session)
        v = _visited(session)
        assert v.get("泰国") and v["泰国"][0]["cities"] == ["曼谷", "清迈", "清莱"], (
            f"纯游览 trip 应完整保留,得到 {v.get('泰国')!r}"
        )

    def test_trip_with_only_non_sightseeing_legs_yields_empty_country(self, session):
        """边界:trip 全是 non-sightseeing leg → 不应出现该国家在 visited 中。"""
        trip = Trip(title="transit-only", start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 1), status="completed")
        session.add(trip)
        _add_leg(session, trip, 0, "斯里巴加湾市", "文莱", date(2024, 1, 1), date(2024, 1, 1),
                 [{"activities": [], "accommodation": "", "transport": ["X-Y 转机"]}])
        session.commit()
        _sync_visited_destinations(session)
        v = _visited(session)
        assert "文莱" not in v, f"全 non-sightseeing 行程不应贡献任何国家,得到 {v!r}"
