from flask import Blueprint, jsonify
from sqlalchemy import func
from database import get_session
from models import Trip, Leg, Expense

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats/overview")
def overview():
    session = get_session()
    try:
        trips = session.query(Trip).filter(Trip.status == "completed").all()
        total_trips = len(trips)
        total_days = sum((t.end_date - t.start_date).days for t in trips)
        countries = set()
        cities = set()
        for t in trips:
            for leg in t.legs:
                countries.add(leg.country)
                cities.add(leg.city)
        total_expense = session.query(func.sum(Expense.amount)).scalar() or 0
        return jsonify({
            "total_trips": total_trips,
            "total_days": total_days,
            "total_countries": len(countries),
            "total_cities": len(cities),
            "total_expense": round(total_expense, 2),
            "avg_expense_per_trip": round(total_expense / total_trips, 2) if total_trips else 0,
        })
    finally:
        session.close()


@stats_bp.route("/api/stats/destinations")
def destinations():
    session = get_session()
    try:
        legs = session.query(Leg).join(Trip).filter(Trip.status == "completed").all()
        country_counts = {}
        city_counts = {}
        for leg in legs:
            country_counts[leg.country] = country_counts.get(leg.country, 0) + 1
            city_counts[leg.city] = city_counts.get(leg.city, 0) + 1
        return jsonify({
            "countries": sorted(country_counts.items(), key=lambda x: -x[1]),
            "cities": sorted(city_counts.items(), key=lambda x: -x[1]),
        })
    finally:
        session.close()


@stats_bp.route("/api/stats/expenses")
def expense_stats():
    session = get_session()
    try:
        by_category = session.query(
            Expense.category, func.sum(Expense.amount)
        ).group_by(Expense.category).all()

        by_trip = session.query(
            Trip.id, Trip.title, func.sum(Expense.amount)
        ).join(Expense).group_by(Trip.id).order_by(Trip.start_date).all()

        trips = session.query(Trip).filter(Trip.status == "completed").all()
        per_day_trend = []
        for t in trips:
            days = max((t.end_date - t.start_date).days, 1)
            total = sum(e.amount for e in t.expenses)
            per_day_trend.append({
                "trip_id": t.id,
                "title": t.title,
                "per_person_per_day": round(total / t.traveler_count / days, 2),
            })

        return jsonify({
            "by_category": [{"category": c, "total": round(t, 2)} for c, t in by_category],
            "by_trip": [{"trip_id": tid, "title": title, "total": round(amt, 2)}
                        for tid, title, amt in by_trip],
            "per_day_trend": per_day_trend,
        })
    finally:
        session.close()
