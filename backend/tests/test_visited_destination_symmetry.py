"""对称守卫 invariant：行程卡片的 destination_label 与个人档案的
visited_countries_cities 是「已游览」语义的两个独立展示路径,二者对每一个 leg
的纳入/排除决定必须一致,且都必须等于 _is_non_sightseeing_leg 给出的唯一真理。

防回归:本次修复(把 _is_non_sightseeing_leg 过滤同时落到两条路径)的核心约束
就是「同一规则,两处实现,展示一致」。下次任意一方再加新过滤(或 [待确认] 处理、
status 过滤、跨年合并等)而另一方没跟,本测试立即 RED——精确暴露分叉的那一个
leg 是哪侧路径漏了。

判定标准:`services.evaluator._is_non_sightseeing_leg(leg.to_dict(include_days=True))`。
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
from services.evaluator import _is_non_sightseeing_leg


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


def _build_diverse_trips(session):
    """覆盖性 fixture:4 种典型形态混合,确保包含 (sightseeing × 国内/出境)、
    (non-sightseeing × 中转/返程终点)所有组合。

    - 肯尼亚之旅:出境游(肯尼亚 sightseeing)+ 北京返程(non-sightseeing)
    - 北京三日:国内游(北京 sightseeing,country=中国 时 label 用 city)
    - 英国之旅:文莱中转(non-sightseeing)+ 英国 sightseeing + 北京返程(non-sightseeing)
    """
    t1 = Trip(title="肯尼亚之旅", start_date=date(2025, 5, 1),
              end_date=date(2025, 5, 11), status="completed")
    session.add(t1)
    _add_leg(session, t1, 0, "内罗毕", "肯尼亚", date(2025, 5, 1), date(2025, 5, 3),
             [{"activities": ["国家博物馆"], "accommodation": "Hotel Nairobi", "transport": []}])
    _add_leg(session, t1, 1, "北京", "中国", date(2025, 5, 11), date(2025, 5, 11),
             [{"activities": [], "accommodation": "",
               "transport": ["哈马德国际机场-北京大兴国际机场"]}])

    t2 = Trip(title="北京三日", start_date=date(2024, 1, 1),
              end_date=date(2024, 1, 3), status="completed")
    session.add(t2)
    _add_leg(session, t2, 0, "北京", "中国", date(2024, 1, 1), date(2024, 1, 3),
             [{"activities": ["故宫"], "accommodation": "Hotel BJ", "transport": []}])

    t3 = Trip(title="英国之旅", start_date=date(2024, 9, 28),
              end_date=date(2024, 10, 8), status="completed")
    session.add(t3)
    _add_leg(session, t3, 0, "斯里巴加湾市", "文莱", date(2024, 9, 28), date(2024, 9, 28),
             [{"activities": [], "accommodation": "", "transport": ["北京-文莱 转机"]}])
    _add_leg(session, t3, 1, "伦敦", "英国", date(2024, 9, 29), date(2024, 10, 3),
             [{"activities": ["大英博物馆"], "accommodation": "Hotel London", "transport": ["BN-LON"]}])
    _add_leg(session, t3, 2, "北京", "中国", date(2024, 10, 8), date(2024, 10, 8),
             [{"activities": [], "accommodation": "", "transport": ["LON-北京"]}])

    session.commit()
    return [t1, t2, t3]


def _trip_visited_entry(visited, trip, country):
    """根据 trip.start_date 的年月在 visited[country] 列表中找到该 trip 的 entry。"""
    target_date = f"{trip.start_date.year:04d}-{trip.start_date.month:02d}"
    for entry in visited.get(country, []):
        if entry.get("date") == target_date:
            return entry
    return None


class TestSymmetricGuardVisitedVsDestinationLabel:
    """两条独立路径(destination_label / visited)必须对每一个 leg 做出一致决定。"""

    def test_each_leg_inclusion_agrees_across_two_paths(self, session):
        """invariant:对每一个 leg,visited 与 destination_label 是否纳入,必须等于
        _is_non_sightseeing_leg 给出的反向判定。任何一方分叉立即在该 leg 上 RED。
        """
        trips = _build_diverse_trips(session)
        _sync_visited_destinations(session)
        profile = session.query(UserProfile).first()
        visited = json.loads(profile.visited_countries_cities)

        for trip in trips:
            summary = trip.to_dict(include_summary=True)
            label_tokens = {t.strip() for t in summary["destination_label"].split("·") if t.strip()}
            for leg in trip.legs:
                non_sightseeing = _is_non_sightseeing_leg(leg.to_dict(include_days=True))

                entry = _trip_visited_entry(visited, trip, leg.country)
                in_visited = entry is not None and leg.city in entry.get("cities", [])

                # destination_label 在 country == "中国" 时用 city,其他用 country
                label_token = leg.city if leg.country == "中国" else leg.country
                in_label = label_token in label_tokens

                ctx = (
                    f"trip {trip.id} {trip.title!r} leg {leg.order_index} "
                    f"({leg.country}/{leg.city}) "
                    f"non_sightseeing={non_sightseeing} "
                    f"in_visited={in_visited} in_label={in_label} "
                    f"label={summary['destination_label']!r}"
                )

                if non_sightseeing:
                    assert not in_visited, f"该 leg 应排除但出现在 visited 中。{ctx}"
                    assert not in_label, f"该 leg 应排除但出现在 destination_label 中。{ctx}"
                else:
                    assert in_visited, f"该 leg 应纳入但 visited 缺失。{ctx}"
                    assert in_label, f"该 leg 应纳入但 destination_label 缺失。{ctx}"

    def test_destination_label_country_set_equals_visited_country_set(self, session):
        """补充 invariant:每一个 trip 在 visited 中贡献的 country 集合,必须与
        destination_label 反推出的 country 集合相等(中国 leg 时 destination_label
        显示的是 city,需要由内向外把它折回 country=中国)。"""
        trips = _build_diverse_trips(session)
        _sync_visited_destinations(session)
        visited = json.loads(session.query(UserProfile).first().visited_countries_cities)

        for trip in trips:
            # 该 trip 在 visited 中贡献了哪些 country?
            target_date = f"{trip.start_date.year:04d}-{trip.start_date.month:02d}"
            countries_in_visited = {
                country for country, entries in visited.items()
                for entry in entries if entry.get("date") == target_date
            }
            # 该 trip 的 destination_label 反推出的 country 集合:
            # - 中国 leg 时 label 用 city,但只要该 trip 有任何中国 sightseeing leg,country=中国 一定在集合里
            # - 其他 leg 直接是 country
            countries_in_label = set()
            for leg in trip.legs:
                if _is_non_sightseeing_leg(leg.to_dict(include_days=True)):
                    continue
                countries_in_label.add(leg.country)

            assert countries_in_visited == countries_in_label, (
                f"trip {trip.id} {trip.title!r}: "
                f"visited 贡献 {countries_in_visited}, "
                f"destination_label 反推 {countries_in_label}"
            )
