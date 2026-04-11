import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_session
from models import Trip, Leg, TripDay, Expense

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "samples", "201910-myanmar.json")


def seed():
    init_db()
    session = get_session()

    if session.query(Trip).count() > 0:
        print("Database already has data, skipping seed.")
        session.close()
        return

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    t = data["trip"]
    trip = Trip(
        title=t["title"],
        start_date=date.fromisoformat(t["start_date"]),
        end_date=date.fromisoformat(t["end_date"]),
        traveler_count=t["traveler_count"],
        description=t.get("description"),
        status=t["status"],
    )
    session.add(trip)
    session.flush()

    leg_map = {}
    for leg_data in data["legs"]:
        leg = Leg(
            trip_id=trip.id,
            order_index=leg_data["order_index"],
            city=leg_data["city"],
            country=leg_data["country"],
            start_date=date.fromisoformat(leg_data["start_date"]),
            end_date=date.fromisoformat(leg_data["end_date"]),
        )
        session.add(leg)
        session.flush()
        leg_map[leg_data["city"]] = leg.id

        for day_data in leg_data.get("days", []):
            day = TripDay(
                leg_id=leg.id,
                day_number=day_data["day_number"],
                date=date.fromisoformat(day_data["date"]),
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
            leg_id=leg_map.get(exp_data.get("leg_city")),
            category=exp_data["category"],
            amount=exp_data["amount"],
            currency=exp_data.get("currency", "CNY"),
            description=exp_data.get("description"),
            date=date.fromisoformat(exp_data["date"]),
        )
        session.add(expense)

    title = trip.title
    n_legs = len(data["legs"])
    n_expenses = len(data.get("expenses", []))
    session.commit()
    session.close()
    print(f"Seeded: {title} ({n_legs} legs, {n_expenses} expenses)")


if __name__ == "__main__":
    seed()
