from flask import Blueprint, jsonify
from sqlalchemy import func, extract
from database import get_session
from models import Trip, Leg, Expense

stats_bp = Blueprint("stats", __name__)


PENDING_PLACEHOLDER = "[待确认]"


@stats_bp.route("/api/stats/overview")
def overview():
    session = get_session()
    try:
        trips = session.query(Trip).filter(Trip.status == "completed", Trip.is_deleted == False).all()  # noqa: E712
        total_trips = len(trips)
        total_days = sum((t.end_date - t.start_date).days for t in trips)
        countries = set()
        cities = set()
        for t in trips:
            for leg in t.legs:
                if leg.country and leg.country != PENDING_PLACEHOLDER:
                    countries.add(leg.country)
                if leg.city and leg.city != PENDING_PLACEHOLDER:
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
        trips = session.query(Trip).filter(Trip.status == "completed", Trip.is_deleted == False).all()  # noqa: E712
        country_counts = {}
        city_counts = {}
        for trip in trips:
            seen_countries = set()
            for leg in trip.legs:
                if leg.country and leg.country != PENDING_PLACEHOLDER and leg.country not in seen_countries:
                    seen_countries.add(leg.country)
                    country_counts[leg.country] = country_counts.get(leg.country, 0) + 1
                if leg.city and leg.city != PENDING_PLACEHOLDER:
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
        ).join(Trip).filter(Trip.is_deleted == False).group_by(Expense.category).all()  # noqa: E712

        by_trip = session.query(
            Trip.id, Trip.title, func.sum(Expense.amount)
        ).join(Expense).filter(Trip.is_deleted == False).group_by(Trip.id).order_by(Trip.start_date).all()  # noqa: E712

        trips = session.query(Trip).filter(Trip.status == "completed", Trip.is_deleted == False).all()  # noqa: E712
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

        return jsonify({
            "by_category": [{"category": c, "total": round(t, 2)} for c, t in by_category],
            "by_trip": [{"trip_id": tid, "title": title, "total": round(amt, 2)}
                        for tid, title, amt in by_trip],
            "per_day_trend": per_day_trend,
            "by_year": [{"year": int(y), "total": round(amt, 2)} for y, amt in by_year],
        })
    finally:
        session.close()
