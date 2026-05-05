import json
from datetime import date
from flask import Blueprint, request, jsonify
from database import get_session
from models import Trip, Leg, TripDay, Expense, TripEvaluation
from routes.profile import _get_or_create_profile
from services.evaluator import _is_non_sightseeing_leg

trips_bp = Blueprint("trips", __name__)


def _sync_visited_destinations(session):
    """汇总已完成行程的 leg，写入 UserProfile.visited_countries_cities。

    按 (trip_id, country) 分组，每次行程独立一条记录，时间取 Trip.start_date 所在年月。
    格式：{country: [{"date": "YYYY-MM", "cities": [...]}, ...]}

    与 Trip.to_dict(include_summary=True) 生成 destination_label 的语义保持一致：
    返程终点 / 纯中转（无任何游览证据）的 leg 不计入「去过的地方」，避免把仅经停
    的城市错误聚合为已去过（典型如返程当日的北京、5h 转机的文莱）。
    """
    trips = (
        session.query(Trip)
        .filter(Trip.status == "completed")
        .filter(Trip.is_deleted == False)  # noqa: E712
        .order_by(Trip.start_date)
        .all()
    )
    # {(trip_id, country): {"date": "YYYY-MM", "cities": [...]}}
    trip_country: dict = {}
    for trip in trips:
        for leg in trip.legs:
            if _is_non_sightseeing_leg(leg.to_dict(include_days=True)):
                continue
            key = (trip.id, leg.country)
            if key not in trip_country:
                trip_country[key] = {
                    "date": f"{trip.start_date.year:04d}-{trip.start_date.month:02d}",
                    "cities": [],
                }
            if leg.city not in trip_country[key]["cities"]:
                trip_country[key]["cities"].append(leg.city)

    nested: dict = {}
    for (_, country), data in trip_country.items():
        nested.setdefault(country, []).append(data)

    profile = _get_or_create_profile(session)
    profile.visited_countries_cities = json.dumps(nested, ensure_ascii=False)
    session.commit()


def _parse_date(s, fallback=None):
    if s:
        return date.fromisoformat(s)
    if fallback:
        return fallback if isinstance(fallback, date) else date.fromisoformat(fallback)
    return None


@trips_bp.route("/api/trips", methods=["GET"])
def list_trips():
    session = get_session()
    try:
        q = session.query(Trip).filter(Trip.is_deleted == False)  # noqa: E712
        status = request.args.get("status")
        year = request.args.get("year")
        search = request.args.get("search")
        if status:
            q = q.filter(Trip.status == status)
        if year:
            q = q.filter(Trip.start_date >= date(int(year), 1, 1),
                         Trip.start_date <= date(int(year), 12, 31))
        if search:
            q = q.filter(Trip.title.contains(search))
        trips = q.order_by(Trip.start_date.desc()).all()
        return jsonify([t.to_dict(include_summary=True) for t in trips])
    finally:
        session.close()


@trips_bp.route("/api/trips/<int:trip_id>", methods=["GET"])
def get_trip(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip or trip.is_deleted:
            return jsonify({"error": "Trip not found"}), 404
        return jsonify(trip.to_dict(include_legs=True, include_expenses=True))
    finally:
        session.close()


@trips_bp.route("/api/trips", methods=["POST"])
def create_trip():
    session = get_session()
    try:
        data = request.json
        trip_start = _parse_date(data.get("start_date"))
        trip_end = _parse_date(data.get("end_date"))
        if not trip_start or not trip_end:
            return jsonify({"error": "请填写行程开始和结束日期"}), 400

        trip = Trip(
            title=data["title"],
            start_date=trip_start,
            end_date=trip_end,
            traveler_count=data.get("traveler_count", 1),
            description=data.get("description"),
            cover_image=data.get("cover_image"),
            status=data.get("status", "completed"),
        )
        session.add(trip)
        session.flush()

        for leg_data in data.get("legs", []):
            leg = Leg(
                trip_id=trip.id,
                order_index=leg_data["order_index"],
                city=leg_data["city"],
                country=leg_data["country"],
                start_date=_parse_date(leg_data.get("start_date"), trip_start),
                end_date=_parse_date(leg_data.get("end_date"), trip_end),
            )
            session.add(leg)
            session.flush()

            for day_data in leg_data.get("days", []):
                day_date = _parse_date(day_data.get("date"), trip_start)
                day = TripDay(
                    leg_id=leg.id,
                    day_number=day_data["day_number"],
                    date=day_date,
                    description=day_data.get("description"),
                    highlights=day_data.get("highlights"),
                    activities=json.dumps(day_data.get("activities", []), ensure_ascii=False),
                    transport=json.dumps(day_data.get("transport", []), ensure_ascii=False),
                    accommodation=day_data.get("accommodation"),
                )
                session.add(day)

        for exp_data in data.get("expenses", []):
            expense = Expense(
                trip_id=trip.id,
                leg_id=exp_data.get("leg_id"),
                trip_day_id=exp_data.get("trip_day_id"),
                category=exp_data["category"],
                amount=exp_data["amount"],
                currency=exp_data.get("currency", "CNY"),
                description=exp_data.get("description"),
                date=_parse_date(exp_data.get("date"), trip_start),
            )
            session.add(expense)

        session.commit()
        try:
            _sync_visited_destinations(session)
        except Exception:
            session.rollback()
        return jsonify(trip.to_dict(include_legs=True, include_expenses=True)), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@trips_bp.route("/api/trips/<int:trip_id>", methods=["PUT"])
def update_trip(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        data = request.json
        for field in ["title", "description", "cover_image", "status"]:
            if field in data:
                setattr(trip, field, data[field])
        if "start_date" in data and data["start_date"]:
            trip.start_date = _parse_date(data["start_date"])
        if "end_date" in data and data["end_date"]:
            trip.end_date = _parse_date(data["end_date"])
        if "traveler_count" in data:
            trip.traveler_count = data["traveler_count"]

        trip_start = trip.start_date
        trip_end = trip.end_date

        if "legs" in data:
            for leg in trip.legs:
                session.delete(leg)
            session.flush()

            for leg_data in data["legs"]:
                leg = Leg(
                    trip_id=trip.id,
                    order_index=leg_data["order_index"],
                    city=leg_data["city"],
                    country=leg_data["country"],
                    start_date=_parse_date(leg_data.get("start_date"), trip_start),
                    end_date=_parse_date(leg_data.get("end_date"), trip_end),
                )
                session.add(leg)
                session.flush()

                for day_data in leg_data.get("days", []):
                    day_date = _parse_date(day_data.get("date"), trip_start)
                    day = TripDay(
                        leg_id=leg.id,
                        day_number=day_data["day_number"],
                        date=day_date,
                        description=day_data.get("description"),
                        highlights=day_data.get("highlights"),
                        activities=json.dumps(day_data.get("activities", []), ensure_ascii=False),
                        transport=json.dumps(day_data.get("transport", []), ensure_ascii=False),
                        accommodation=day_data.get("accommodation"),
                    )
                    session.add(day)

        if "expenses" in data:
            for exp in trip.expenses:
                session.delete(exp)
            session.flush()

            for exp_data in data["expenses"]:
                expense = Expense(
                    trip_id=trip.id,
                    category=exp_data["category"],
                    amount=exp_data["amount"],
                    currency=exp_data.get("currency", "CNY"),
                    description=exp_data.get("description"),
                    date=_parse_date(exp_data.get("date"), trip_start),
                )
                session.add(expense)

        # 行程数据有变更 → 同步使评价缓存失效，下次 GET 会基于新数据重新生成。
        # 否则用户会看到基于过期 leg/day/expense 的旧"遗漏景点"和"花费评分"。
        for ev in session.query(TripEvaluation).filter_by(trip_id=trip.id).all():
            session.delete(ev)

        session.commit()
        try:
            _sync_visited_destinations(session)
        except Exception:
            session.rollback()
        return jsonify(trip.to_dict(include_legs=True, include_expenses=True))
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@trips_bp.route("/api/trips/<int:trip_id>", methods=["DELETE"])
def delete_trip(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404
        trip.is_deleted = True
        session.commit()
        return jsonify({"deleted": trip_id})
    finally:
        session.close()


@trips_bp.route("/api/trip-days/<int:day_id>/activities", methods=["PATCH"])
def patch_trip_day_activities(day_id):
    session = get_session()
    try:
        data = request.json or {}
        if "activity" not in data:
            return jsonify({"error": "activity is required"}), 400

        day = session.query(TripDay).get(day_id)
        if not day:
            return jsonify({"error": "Trip day not found"}), 404

        try:
            activities = json.loads(day.activities) if day.activities else []
        except json.JSONDecodeError:
            activities = []
        if not isinstance(activities, list):
            activities = []

        activity = data["activity"]
        if activity not in activities:
            activities.append(activity)

        day.activities = json.dumps(activities, ensure_ascii=False)
        session.commit()
        return jsonify(day.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()
