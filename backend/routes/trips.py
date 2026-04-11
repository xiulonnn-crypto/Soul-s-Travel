import json
from datetime import date
from flask import Blueprint, request, jsonify
from database import get_session
from models import Trip, Leg, TripDay, Expense
from routes.profile import _get_or_create_profile

trips_bp = Blueprint("trips", __name__)


def _sync_visited_destinations(session):
    """汇总已完成行程的 leg，写入 UserProfile.visited_countries_cities。"""
    rows = (
        session.query(Leg.country, Leg.city, Leg.start_date)
        .join(Trip, Leg.trip_id == Trip.id)
        .filter(Trip.status == "completed")
        .filter(Trip.is_deleted == False)  # noqa: E712
        .all()
    )
    earliest = {}
    for country, city, start_date in rows:
        key = (country, city)
        if key not in earliest or start_date < earliest[key]:
            earliest[key] = start_date
    nested = {}
    for (country, city), d in earliest.items():
        nested.setdefault(country, {})[city] = f"{d.year:04d}-{d.month:02d}"
    profile = _get_or_create_profile(session)
    profile.visited_countries_cities = json.dumps(nested, ensure_ascii=False)
    session.commit()


def _parse_date(s):
    return date.fromisoformat(s)


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
        return jsonify([t.to_dict() for t in trips])
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
        trip = Trip(
            title=data["title"],
            start_date=_parse_date(data["start_date"]),
            end_date=_parse_date(data["end_date"]),
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
                start_date=_parse_date(leg_data["start_date"]),
                end_date=_parse_date(leg_data["end_date"]),
            )
            session.add(leg)
            session.flush()

            for day_data in leg_data.get("days", []):
                day = TripDay(
                    leg_id=leg.id,
                    day_number=day_data["day_number"],
                    date=_parse_date(day_data["date"]),
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
                date=_parse_date(exp_data["date"]),
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
        if "start_date" in data:
            trip.start_date = _parse_date(data["start_date"])
        if "end_date" in data:
            trip.end_date = _parse_date(data["end_date"])
        if "traveler_count" in data:
            trip.traveler_count = data["traveler_count"]

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
                    start_date=_parse_date(leg_data["start_date"]),
                    end_date=_parse_date(leg_data["end_date"]),
                )
                session.add(leg)
                session.flush()

                for day_data in leg_data.get("days", []):
                    day = TripDay(
                        leg_id=leg.id,
                        day_number=day_data["day_number"],
                        date=_parse_date(day_data["date"]),
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
                    date=_parse_date(exp_data["date"]),
                )
                session.add(expense)

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
