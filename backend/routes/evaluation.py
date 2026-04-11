import json
from flask import Blueprint, jsonify
from database import get_session
from models import Trip, TripEvaluation
from services.evaluator import generate_evaluation

evaluation_bp = Blueprint("evaluation", __name__)


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
        result = generate_evaluation(trip_dict)

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
        result = generate_evaluation(trip_dict)

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
