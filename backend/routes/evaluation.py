import json
from flask import Blueprint, jsonify
from database import get_session
from models import Trip, Leg, TripEvaluation
from services.evaluator import generate_evaluation
from routes.profile import _get_or_create_profile

evaluation_bp = Blueprint("evaluation", __name__)


def _build_past_visited(session, trip_id, legs):
    """从历史行程中收集当前行程各城市已访景点。

    返回 {city: [activity, ...]}，仅包含 trip_id 以外的已完成未删除行程。
    """
    cities = [leg.get("city", "") for leg in legs if leg.get("city")]
    if not cities:
        return {}

    past_visited = {}
    past_legs = (
        session.query(Leg)
        .join(Trip, Leg.trip_id == Trip.id)
        .filter(
            Trip.id != trip_id,
            Trip.is_deleted == False,
            Trip.status == "completed",
            Leg.city.in_(cities),
        )
        .all()
    )
    for leg in past_legs:
        city = leg.city
        if city not in past_visited:
            past_visited[city] = set()
        for day in leg.days:
            acts = json.loads(day.activities) if day.activities else []
            past_visited[city].update(acts)

    return {city: list(acts) for city, acts in past_visited.items()}


@evaluation_bp.route("/api/trips/<int:trip_id>/evaluation", methods=["GET"])
def get_evaluation(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        existing = session.query(TripEvaluation).filter_by(trip_id=trip_id).first()
        if existing:
            return jsonify(existing.to_dict())

        trip_dict = trip.to_dict(include_legs=True, include_expenses=True)
        profile = _get_or_create_profile(session)
        profile_dict = profile.to_dict()
        past_visited = _build_past_visited(session, trip_id, trip_dict.get("legs", []))
        result = generate_evaluation(trip_dict, profile=profile_dict, past_visited=past_visited)

        evaluation = TripEvaluation(
            trip_id=trip_id,
            overall_score=result["overall_score"],
            evaluation_data=json.dumps(result["evaluation_data"], ensure_ascii=False),
        )
        session.add(evaluation)
        session.commit()
        return jsonify(evaluation.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@evaluation_bp.route("/api/trips/<int:trip_id>/evaluation", methods=["POST"])
def regenerate_evaluation(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        existing = session.query(TripEvaluation).filter_by(trip_id=trip_id).first()
        if existing:
            session.delete(existing)
            session.flush()

        trip_dict = trip.to_dict(include_legs=True, include_expenses=True)
        profile = _get_or_create_profile(session)
        profile_dict = profile.to_dict()
        past_visited = _build_past_visited(session, trip_id, trip_dict.get("legs", []))
        result = generate_evaluation(trip_dict, profile=profile_dict, past_visited=past_visited)

        evaluation = TripEvaluation(
            trip_id=trip_id,
            overall_score=result["overall_score"],
            evaluation_data=json.dumps(result["evaluation_data"], ensure_ascii=False),
        )
        session.add(evaluation)
        session.commit()
        return jsonify(evaluation.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
