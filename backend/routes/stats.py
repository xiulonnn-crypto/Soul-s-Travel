from collections import Counter, defaultdict
from flask import Blueprint, jsonify
from sqlalchemy import func, extract
from database import get_session
from models import Trip, Expense, TripEvaluation
from services.continent_map import get_continent, TOTAL_WORLD_COUNTRIES

stats_bp = Blueprint("stats", __name__)


PENDING_PLACEHOLDER = "[待确认]"


def _completed_trips(session):
    return session.query(Trip).filter(
        Trip.status == "completed", Trip.is_deleted == False  # noqa: E712
    ).all()


def _trip_countries(trip):
    """返回 trip 去重后的国家列表（排除待确认），顺序按 leg 顺序。"""
    seen = []
    for leg in trip.legs:
        if leg.country and leg.country != PENDING_PLACEHOLDER and leg.country not in seen:
            seen.append(leg.country)
    return seen


def _trip_primary_country(trip):
    """返回该 trip 的代表国家：leg 数最多的国家。用于按国家归属花费。"""
    counter = Counter()
    for leg in trip.legs:
        if leg.country and leg.country != PENDING_PLACEHOLDER:
            counter[leg.country] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _trip_destination_label(trip):
    """以 leg 顺序拼出目的地标签，中国展示城市，其他国家展示国家名。"""
    seen = []
    for leg in trip.legs:
        label = leg.city if leg.country == "中国" else leg.country
        if label and label != PENDING_PLACEHOLDER and label not in seen:
            seen.append(label)
    return " · ".join(seen)


def _companion_type(count):
    if not count or count <= 1:
        return "独行"
    if count == 2:
        return "结伴"
    return "家庭/多人"


@stats_bp.route("/api/stats/overview")
def overview():
    session = get_session()
    try:
        trips = _completed_trips(session)
        total_trips = len(trips)
        total_days = sum((t.end_date - t.start_date).days for t in trips)
        countries = set()
        cities = set()
        continents = set()
        for t in trips:
            for leg in t.legs:
                if leg.country and leg.country != PENDING_PLACEHOLDER:
                    countries.add(leg.country)
                    continents.add(get_continent(leg.country))
                if leg.city and leg.city != PENDING_PLACEHOLDER:
                    cities.add(leg.city)
        total_expense = session.query(func.sum(Expense.amount)).scalar() or 0

        first_trip_date = min((t.start_date for t in trips), default=None)
        last_trip_date = max((t.start_date for t in trips), default=None)
        world_coverage = round(len(countries) / TOTAL_WORLD_COUNTRIES * 100, 1)

        return jsonify({
            "total_trips": total_trips,
            "total_days": total_days,
            "total_countries": len(countries),
            "total_cities": len(cities),
            "total_continents": len([c for c in continents if c != "其他"]),
            "total_expense": round(total_expense, 2),
            "avg_expense_per_trip": round(total_expense / total_trips, 2) if total_trips else 0,
            "first_trip_date": first_trip_date.isoformat() if first_trip_date else None,
            "last_trip_date": last_trip_date.isoformat() if last_trip_date else None,
            "world_coverage": world_coverage,
        })
    finally:
        session.close()


@stats_bp.route("/api/stats/destinations")
def destinations():
    session = get_session()
    try:
        trips = _completed_trips(session)
        country_counts = {}
        city_counts = {}
        continent_countries = defaultdict(set)
        continent_trips = Counter()
        for trip in trips:
            trip_countries = _trip_countries(trip)
            trip_continents_seen = set()
            for country in trip_countries:
                country_counts[country] = country_counts.get(country, 0) + 1
                cont = get_continent(country)
                continent_countries[cont].add(country)
                trip_continents_seen.add(cont)
            for cont in trip_continents_seen:
                continent_trips[cont] += 1
            for leg in trip.legs:
                if leg.city and leg.city != PENDING_PLACEHOLDER:
                    city_counts[leg.city] = city_counts.get(leg.city, 0) + 1

        by_continent = sorted(
            [
                {
                    "continent": cont,
                    "country_count": len(countries),
                    "trip_count": continent_trips[cont],
                    "countries": sorted(countries),
                }
                for cont, countries in continent_countries.items()
            ],
            key=lambda x: -x["country_count"],
        )

        return jsonify({
            "countries": sorted(country_counts.items(), key=lambda x: -x[1]),
            "cities": sorted(city_counts.items(), key=lambda x: -x[1]),
            "by_continent": by_continent,
        })
    finally:
        session.close()


@stats_bp.route("/api/stats/expenses")
def expense_stats():
    session = get_session()
    try:
        by_category = session.query(
            Expense.category, func.sum(Expense.amount)
        ).join(Trip).filter(Trip.is_deleted == False).group_by(Expense.category).all()  # noqa: E712

        by_trip = session.query(
            Trip.id, Trip.title, func.sum(Expense.amount)
        ).join(Expense).filter(Trip.is_deleted == False).group_by(Trip.id).order_by(Trip.start_date).all()  # noqa: E712

        trips = _completed_trips(session)
        per_day_trend = []
        for t in trips:
            days = max((t.end_date - t.start_date).days, 1)
            total = sum(e.amount for e in t.expenses)
            per_day_trend.append({
                "trip_id": t.id,
                "title": t.title,
                "per_person_per_day": round(total / t.traveler_count / days, 2),
            })

        by_year = session.query(
            extract("year", Trip.start_date).label("year"),
            func.sum(Expense.amount),
        ).join(Expense).filter(
            Trip.is_deleted == False  # noqa: E712
        ).group_by("year").order_by("year").all()

        country_totals = defaultdict(float)
        for t in trips:
            country = _trip_primary_country(t)
            if not country:
                continue
            country_totals[country] += sum(e.amount for e in t.expenses)
        by_country = sorted(
            [{"country": c, "total": round(v, 2)} for c, v in country_totals.items()],
            key=lambda x: -x["total"],
        )

        return jsonify({
            "by_category": [{"category": c, "total": round(t, 2)} for c, t in by_category],
            "by_trip": [{"trip_id": tid, "title": title, "total": round(amt, 2)}
                        for tid, title, amt in by_trip],
            "per_day_trend": per_day_trend,
            "by_year": [{"year": int(y), "total": round(amt, 2)} for y, amt in by_year],
            "by_country": by_country,
        })
    finally:
        session.close()


def _trip_total_expense(trip):
    return sum(e.amount for e in trip.expenses)


def _trip_per_person_per_day(trip):
    days = max((trip.end_date - trip.start_date).days, 1)
    travelers = trip.traveler_count or 1
    total = _trip_total_expense(trip)
    return total / travelers / days


def _highlight_card(trip, value_label, value):
    return {
        "trip_id": trip.id,
        "title": trip.title,
        "destination_label": _trip_destination_label(trip),
        "start_date": trip.start_date.isoformat(),
        "value_label": value_label,
        "value": value,
    }


@stats_bp.route("/api/stats/highlights")
def highlights():
    """旅行之最：最早 / 最长 / 最贵 / 最省 / 评分最高 / 评分最低。"""
    session = get_session()
    try:
        trips = _completed_trips(session)
        result = {
            "earliest": None,
            "longest": None,
            "most_expensive": None,
            "cheapest_per_day": None,
            "highest_rated": None,
            "lowest_rated": None,
        }
        if not trips:
            return jsonify(result)

        earliest = min(trips, key=lambda t: t.start_date)
        result["earliest"] = _highlight_card(
            earliest, "出发日期", earliest.start_date.isoformat()
        )

        longest = max(trips, key=lambda t: (t.end_date - t.start_date).days)
        longest_days = (longest.end_date - longest.start_date).days
        result["longest"] = _highlight_card(longest, "天数", f"{longest_days} 天")

        trips_with_expense = [t for t in trips if _trip_total_expense(t) > 0]
        if trips_with_expense:
            most_exp = max(trips_with_expense, key=_trip_total_expense)
            result["most_expensive"] = _highlight_card(
                most_exp, "总花费", f"¥{round(_trip_total_expense(most_exp)):,}"
            )
            # 排除异常低（人均日 <50 元）避免错账干扰
            valid_cheap = [t for t in trips_with_expense if _trip_per_person_per_day(t) >= 50]
            if valid_cheap:
                cheap = min(valid_cheap, key=_trip_per_person_per_day)
                result["cheapest_per_day"] = _highlight_card(
                    cheap, "人均日花费", f"¥{round(_trip_per_person_per_day(cheap))}"
                )

        rated = session.query(Trip).join(TripEvaluation).filter(
            Trip.status == "completed", Trip.is_deleted == False  # noqa: E712
        ).all()
        if rated:
            highest = max(rated, key=lambda t: t.evaluation.overall_score)
            lowest = min(rated, key=lambda t: t.evaluation.overall_score)
            result["highest_rated"] = _highlight_card(
                highest, "评分", f"{highest.evaluation.overall_score} 分"
            )
            if lowest.id != highest.id:
                result["lowest_rated"] = _highlight_card(
                    lowest, "评分", f"{lowest.evaluation.overall_score} 分"
                )

        return jsonify(result)
    finally:
        session.close()


@stats_bp.route("/api/stats/timeline")
def timeline():
    """时间与同行画像：月份分布 + 旅伴类型。"""
    session = get_session()
    try:
        trips = _completed_trips(session)
        by_month = [{"month": m, "trip_count": 0} for m in range(1, 13)]
        companion = Counter()
        for t in trips:
            by_month[t.start_date.month - 1]["trip_count"] += 1
            companion[_companion_type(t.traveler_count)] += 1

        companion_order = ["独行", "结伴", "家庭/多人"]
        by_companion = [
            {"type": t, "count": companion.get(t, 0)} for t in companion_order
        ]

        return jsonify({
            "by_month": by_month,
            "by_companion": by_companion,
        })
    finally:
        session.close()
