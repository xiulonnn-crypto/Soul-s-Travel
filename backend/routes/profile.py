from flask import Blueprint, jsonify, request
from database import get_session
from models import UserProfile

profile_bp = Blueprint("profile", __name__)


def _get_or_create_profile(session):
    profile = session.query(UserProfile).first()
    if profile:
        return profile
    profile = UserProfile(
        household_income=1600000,
        annual_travel_budget=100000,
        family_description="夫妻两人",
        visited_countries_cities="{}",
    )
    session.add(profile)
    session.commit()
    return profile


@profile_bp.route("/api/profile", methods=["GET"])
def get_profile():
    session = get_session()
    try:
        profile = _get_or_create_profile(session)
        return jsonify(profile.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@profile_bp.route("/api/profile", methods=["PUT"])
def update_profile():
    session = get_session()
    try:
        body = request.get_json(silent=True)
        if body is None or not isinstance(body, dict):
            return jsonify({"error": "Invalid JSON body"}), 400

        profile = _get_or_create_profile(session)

        if "household_income" in body:
            v = body["household_income"]
            if not isinstance(v, (int, float)):
                return jsonify({"error": "household_income must be a number"}), 400
            profile.household_income = float(v)

        if "annual_travel_budget" in body:
            v = body["annual_travel_budget"]
            if not isinstance(v, (int, float)):
                return jsonify({"error": "annual_travel_budget must be a number"}), 400
            profile.annual_travel_budget = float(v)

        if "family_description" in body:
            v = body["family_description"]
            if v is not None and not isinstance(v, str):
                return jsonify({"error": "family_description must be a string"}), 400
            profile.family_description = v

        session.commit()
        return jsonify(profile.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
