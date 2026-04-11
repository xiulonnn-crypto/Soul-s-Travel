import uuid
from flask import Blueprint, jsonify
from database import get_session
from models import Trip

share_bp = Blueprint("share", __name__)


@share_bp.route("/api/trips/<int:trip_id>/share", methods=["POST"])
def create_share(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404
        if not trip.share_token:
            trip.share_token = uuid.uuid4().hex[:12]
            session.commit()
        return jsonify({"share_token": trip.share_token})
    finally:
        session.close()


@share_bp.route("/api/trips/<int:trip_id>/share", methods=["DELETE"])
def revoke_share(trip_id):
    session = get_session()
    try:
        trip = session.query(Trip).get(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404
        trip.share_token = None
        session.commit()
        return jsonify({"message": "Share revoked"})
    finally:
        session.close()


@share_bp.route("/api/share/<token>")
def get_shared_trip(token):
    session = get_session()
    try:
        trip = session.query(Trip).filter(Trip.share_token == token).first()
        if not trip:
            return jsonify({"error": "Not found"}), 404
        return jsonify(trip.to_dict(include_legs=True, include_expenses=True))
    finally:
        session.close()
