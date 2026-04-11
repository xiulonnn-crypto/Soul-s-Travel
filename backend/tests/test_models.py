import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Trip, Leg, TripDay, Expense


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()


def test_create_trip(session):
    trip = Trip(title="Test Trip", start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 7), traveler_count=2, status="completed")
    session.add(trip)
    session.commit()
    assert trip.id is not None
    assert trip.to_dict()["title"] == "Test Trip"


def test_trip_with_legs_and_days(session):
    trip = Trip(title="Multi-city", start_date=date(2024, 3, 1),
                end_date=date(2024, 3, 5), status="completed")
    leg = Leg(trip=trip, order_index=1, city="Tokyo", country="Japan",
              start_date=date(2024, 3, 1), end_date=date(2024, 3, 3))
    day = TripDay(leg=leg, day_number=1, date=date(2024, 3, 1),
                  description="Arrival", activities='["Shibuya","Shinjuku"]',
                  transport='["Flight NRT"]', accommodation="Hotel A")
    session.add_all([trip, leg, day])
    session.commit()

    d = trip.to_dict(include_legs=True)
    assert len(d["legs"]) == 1
    assert len(d["legs"][0]["days"]) == 1
    assert d["legs"][0]["days"][0]["activities"] == ["Shibuya", "Shinjuku"]


def test_expense_relations(session):
    trip = Trip(title="Expense Test", start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 3), status="completed")
    expense = Expense(trip=trip, category="交通", amount=3000.0,
                      currency="CNY", description="Flight", date=date(2024, 1, 1))
    session.add_all([trip, expense])
    session.commit()

    d = trip.to_dict(include_expenses=True)
    assert len(d["expenses"]) == 1
    assert d["expenses"][0]["amount"] == 3000.0


def test_cascade_delete(session):
    trip = Trip(title="Delete Test", start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 2), status="completed")
    leg = Leg(trip=trip, order_index=1, city="A", country="B",
              start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))
    day = TripDay(leg=leg, day_number=1, date=date(2024, 1, 1))
    session.add_all([trip, leg, day])
    session.commit()

    session.delete(trip)
    session.commit()
    assert session.query(Leg).count() == 0
    assert session.query(TripDay).count() == 0
