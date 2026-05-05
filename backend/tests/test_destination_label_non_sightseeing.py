"""Trip.to_dict(include_summary=True) 生成的 destination_label
应排除「无任何游览证据的 leg」(返程终点 / 中转 / 起讫点)。

复现 bug：trip 10 (英国行) 卡片显示 "文莱 · 英国 · 北京"，
其中文莱(5h 中转)和北京(返程到家)实际上不是真正去玩的目的地。
trip 13 (肯尼亚) 同理显示 "肯尼亚 · 北京"。

修复后：destination_label 应复用 services.evaluator._is_non_sightseeing_leg
判定，把这类 leg 从 label 中过滤掉，与评分系统的语义保持一致。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Trip, Leg, TripDay


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()


def _build_trip_with_return_home(session):
    """构造 trip 13 的最小复现：肯尼亚 4 个游览 leg + 北京返程 leg。

    北京 leg 仅有 1 个 day，activities=[]，accommodation 空，
    transport 含跨境航班 → 落入 _is_non_sightseeing_leg 判定。
    """
    trip = Trip(title="kenya-trip", start_date=date(2025, 5, 1),
                end_date=date(2025, 5, 11), status="completed")
    legs_data = [
        ("内罗毕", "肯尼亚", date(2025, 5, 1), date(2025, 5, 3),
         [{"activities": ["国家博物馆"], "accommodation": "Hotel Nairobi", "transport": []}]),
        ("马赛马拉国家保护区", "肯尼亚", date(2025, 5, 3), date(2025, 5, 7),
         [{"activities": ["大草原 Safari"], "accommodation": "Mara Camp", "transport": []}]),
        ("纳库鲁", "肯尼亚", date(2025, 5, 7), date(2025, 5, 9),
         [{"activities": ["纳库鲁湖国家公园"], "accommodation": "Hotel Nakuru", "transport": []}]),
        ("奈瓦沙", "肯尼亚", date(2025, 5, 9), date(2025, 5, 10),
         [{"activities": ["奈瓦沙湖"], "accommodation": "Hotel Naivasha", "transport": []}]),
        ("北京", "中国", date(2025, 5, 11), date(2025, 5, 11),
         [{"activities": [], "accommodation": "",
           "transport": ["哈马德国际机场 01:45-北京大兴国际机场 14:40"]}]),
    ]
    for i, (city, country, sd, ed, days) in enumerate(legs_data):
        leg = Leg(trip=trip, order_index=i, city=city, country=country,
                  start_date=sd, end_date=ed)
        session.add(leg)
        for j, day in enumerate(days):
            session.add(TripDay(
                leg=leg, day_number=j + 1, date=sd,
                activities=json.dumps(day["activities"], ensure_ascii=False),
                transport=json.dumps(day["transport"], ensure_ascii=False),
                accommodation=day["accommodation"],
            ))
    session.add(trip)
    session.commit()
    return trip


def _build_trip_with_transit_and_return_home(session):
    """构造 trip 10 的最小复现：文莱 5h 中转 + 伦敦 + 爱丁堡 + 北京返程。

    文莱：activities=[]，accommodation 空，transport 含跨境 → 非游览
    伦敦/爱丁堡：含游览活动 → 游览 leg
    北京：activities=[]，accommodation 空 → 非游览
    """
    trip = Trip(title="uk-trip", start_date=date(2024, 9, 28),
                end_date=date(2024, 10, 8), status="completed")
    legs_data = [
        ("斯里巴加湾市", "文莱", date(2024, 9, 28), date(2024, 9, 28),
         [{"activities": [], "accommodation": "",
           "transport": ["北京-斯里巴加湾市 转机"]}]),
        ("伦敦", "英国", date(2024, 9, 29), date(2024, 10, 3),
         [{"activities": ["大英博物馆"], "accommodation": "Hotel London",
           "transport": ["BN-LON"]}]),
        ("爱丁堡", "英国", date(2024, 10, 3), date(2024, 10, 7),
         [{"activities": ["爱丁堡城堡"], "accommodation": "Hotel Edinburgh",
           "transport": ["LON-EDI"]}]),
        ("北京", "中国", date(2024, 10, 8), date(2024, 10, 8),
         [{"activities": [], "accommodation": "",
           "transport": ["伦敦-北京"]}]),
    ]
    for i, (city, country, sd, ed, days) in enumerate(legs_data):
        leg = Leg(trip=trip, order_index=i, city=city, country=country,
                  start_date=sd, end_date=ed)
        session.add(leg)
        for j, day in enumerate(days):
            session.add(TripDay(
                leg=leg, day_number=j + 1, date=sd,
                activities=json.dumps(day["activities"], ensure_ascii=False),
                transport=json.dumps(day["transport"], ensure_ascii=False),
                accommodation=day["accommodation"],
            ))
    session.add(trip)
    session.commit()
    return trip


def _build_trip_all_sightseeing(session):
    """对照组：trip 9 (泰国) — 3 个 leg 全部含游览活动，destination_label 不应受影响。"""
    trip = Trip(title="thai-trip", start_date=date(2024, 9, 15),
                end_date=date(2024, 9, 22), status="completed")
    legs_data = [
        ("曼谷", "泰国", date(2024, 9, 15), date(2024, 9, 18),
         [{"activities": ["大皇宫"], "accommodation": "Hotel BKK", "transport": []}]),
        ("清迈", "泰国", date(2024, 9, 18), date(2024, 9, 20),
         [{"activities": ["双龙寺"], "accommodation": "Hotel CNX", "transport": []}]),
        ("清莱", "泰国", date(2024, 9, 20), date(2024, 9, 22),
         [{"activities": ["白庙"], "accommodation": "Hotel CEI", "transport": []}]),
    ]
    for i, (city, country, sd, ed, days) in enumerate(legs_data):
        leg = Leg(trip=trip, order_index=i, city=city, country=country,
                  start_date=sd, end_date=ed)
        session.add(leg)
        for j, day in enumerate(days):
            session.add(TripDay(
                leg=leg, day_number=j + 1, date=sd,
                activities=json.dumps(day["activities"], ensure_ascii=False),
                transport=json.dumps(day["transport"], ensure_ascii=False),
                accommodation=day["accommodation"],
            ))
    session.add(trip)
    session.commit()
    return trip


class TestDestinationLabelExcludesNonSightseeing:
    """destination_label 应排除返程终点 / 纯中转的非游览 leg。"""

    def test_kenya_trip_excludes_beijing_return_home(self, session):
        """trip 13: 4 个肯尼亚 leg + 北京返程 → 'destination_label' 应为 '肯尼亚'，不带 '· 北京'。"""
        trip = _build_trip_with_return_home(session)
        d = trip.to_dict(include_summary=True)
        assert d["destination_label"] == "肯尼亚", (
            f"期望排除北京返程 leg，得到 destination_label={d['destination_label']!r}"
        )

    def test_uk_trip_excludes_brunei_transit_and_beijing_return(self, session):
        """trip 10: 文莱中转 + 伦敦 + 爱丁堡 + 北京返程 → 'destination_label' 应为 '英国'。"""
        trip = _build_trip_with_transit_and_return_home(session)
        d = trip.to_dict(include_summary=True)
        assert d["destination_label"] == "英国", (
            f"期望排除文莱中转和北京返程，得到 destination_label={d['destination_label']!r}"
        )

    def test_thailand_trip_unchanged_when_no_transit(self, session):
        """对照组：纯游览 trip 不受影响，3 个 leg 全部 dedup 为单个 '泰国'。"""
        trip = _build_trip_all_sightseeing(session)
        d = trip.to_dict(include_summary=True)
        assert d["destination_label"] == "泰国"

    def test_leg_count_unchanged(self, session):
        """leg_count 仍代表行程的全部 leg 数（含返程），不被该过滤改变。"""
        trip = _build_trip_with_return_home(session)
        d = trip.to_dict(include_summary=True)
        assert d["leg_count"] == 5, "leg_count 应保留全部 leg 数（含返程）"
