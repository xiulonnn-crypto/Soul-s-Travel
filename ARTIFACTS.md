# Soul's Travel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal travel experience management website with AI-assisted trip entry, multi-dimensional statistics, timeline view, and shareable trip links.

**Architecture:** Flask REST backend with SQLAlchemy ORM over SQLite, serving a React 18 SPA. Claude API handles PDF/text parsing into structured trip data. The data model uses a hierarchical Trip > Leg > TripDay structure with optional Expense records at each level.

**Tech Stack:** Python 3 / Flask / SQLAlchemy / pdfplumber / Anthropic SDK | React 18 / Vite / React Router / Ant Design / Recharts / Axios

---

## File Map

### Backend (`backend/`)


| File                    | Responsibility                                                         |
| ----------------------- | ---------------------------------------------------------------------- |
| `app.py`                | Flask application factory, register blueprints, CORS, run on port 5001 |
| `database.py`           | SQLAlchemy engine + session, `init_db()` to create tables              |
| `models.py`             | Trip, Leg, TripDay, Expense ORM models with `to_dict()` serialization  |
| `routes/__init__.py`    | Empty package init                                                     |
| `routes/trips.py`       | Blueprint `trips_bp`: CRUD for trips with nested legs/days/expenses    |
| `routes/stats.py`       | Blueprint `stats_bp`: overview, destinations, expenses aggregation     |
| `routes/share.py`       | Blueprint `share_bp`: generate/revoke share token, public trip query   |
| `routes/parse.py`       | Blueprint `parse_bp`: PDF upload + text parsing via Claude             |
| `services/__init__.py`  | Empty package init                                                     |
| `services/ai_parser.py` | Claude API call with system prompt, JSON schema, response validation   |
| `seed.py`               | Load `data/samples/201910-myanmar.json` into database                  |
| `requirements.txt`      | Python dependencies                                                    |
| `tests/test_models.py`  | Model unit tests                                                       |
| `tests/test_trips.py`   | Trip API integration tests                                             |
| `tests/test_stats.py`   | Stats API tests                                                        |
| `tests/test_share.py`   | Share API tests                                                        |


### Frontend (`frontend/`)


| File                              | Responsibility                                   |
| --------------------------------- | ------------------------------------------------ |
| `vite.config.js`                  | Vite config with `/api` proxy to `:5001`         |
| `src/main.jsx`                    | React entry, render App                          |
| `src/App.jsx`                     | React Router routes definition                   |
| `src/services/api.js`             | Axios instance with interceptors                 |
| `src/components/Layout.jsx`       | 72px icon sidebar + content area                 |
| `src/components/TripCard.jsx`     | PiTravel-style pastel horizontal card            |
| `src/components/ChatPanel.jsx`    | AI chat panel with message bubbles               |
| `src/components/TripForm.jsx`     | Structured trip form with dirty flag             |
| `src/components/ExpenseTable.jsx` | Expense list/summary display                     |
| `src/components/TimelineNode.jsx` | Single timeline entry card                       |
| `src/components/StatsChart.jsx`   | Recharts wrapper components                      |
| `src/pages/Home.jsx`              | Dashboard: stat pills + recent trips             |
| `src/pages/TripList.jsx`          | Trip list with filters                           |
| `src/pages/TripDetail.jsx`        | Trip detail: legs, day timeline, expense sidebar |
| `src/pages/TripEditor.jsx`        | Split view: ChatPanel + TripForm                 |
| `src/pages/Timeline.jsx`          | Vertical timeline grouped by year                |
| `src/pages/Stats.jsx`             | Stats dashboard with charts                      |
| `src/pages/ShareView.jsx`         | Public read-only trip view                       |


---

## Task 1: Backend Scaffold + Data Models

**Files:**

- Create: `backend/requirements.txt`
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/app.py`
- Create: `backend/routes/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/tests/test_models.py`
- **Step 1: Create requirements.txt**

```
backend/requirements.txt
```

```text
flask==3.1.1
flask-cors==5.0.1
sqlalchemy==2.0.41
pdfplumber==0.11.6
anthropic==0.52.0
pytest==8.3.5
```

- **Step 2: Install dependencies**

Run: `cd backend && pip3 install -r requirements.txt`

- **Step 3: Create database.py**

```
backend/database.py
```

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "travel.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()


def get_session():
    return Session()


def init_db():
    from models import Trip, Leg, TripDay, Expense  # noqa: F401
    Base.metadata.create_all(engine)
```

- **Step 4: Create models.py**

```
backend/models.py
```

```python
import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Text, Float, Date, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    traveler_count = Column(Integer, default=1)
    description = Column(Text)
    cover_image = Column(Text)
    share_token = Column(Text, unique=True)
    status = Column(Text, default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    legs = relationship("Leg", back_populates="trip", cascade="all, delete-orphan",
                        order_by="Leg.order_index")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")

    def to_dict(self, include_legs=False, include_expenses=False):
        d = {
            "id": self.id,
            "title": self.title,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "traveler_count": self.traveler_count,
            "description": self.description,
            "cover_image": self.cover_image,
            "share_token": self.share_token,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_legs:
            d["legs"] = [leg.to_dict(include_days=True) for leg in self.legs]
        if include_expenses:
            d["expenses"] = [e.to_dict() for e in self.expenses]
        return d


class Leg(Base):
    __tablename__ = "legs"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    city = Column(Text, nullable=False)
    country = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    trip = relationship("Trip", back_populates="legs")
    days = relationship("TripDay", back_populates="leg", cascade="all, delete-orphan",
                        order_by="TripDay.day_number")
    expenses = relationship("Expense", back_populates="leg")

    def to_dict(self, include_days=False):
        d = {
            "id": self.id,
            "trip_id": self.trip_id,
            "order_index": self.order_index,
            "city": self.city,
            "country": self.country,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }
        if include_days:
            d["days"] = [day.to_dict() for day in self.days]
        return d


class TripDay(Base):
    __tablename__ = "trip_days"

    id = Column(Integer, primary_key=True)
    leg_id = Column(Integer, ForeignKey("legs.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(Text)
    highlights = Column(Text)
    activities = Column(Text, default="[]")
    transport = Column(Text, default="[]")
    accommodation = Column(Text)

    leg = relationship("Leg", back_populates="days")
    expenses = relationship("Expense", back_populates="trip_day")

    def to_dict(self):
        return {
            "id": self.id,
            "leg_id": self.leg_id,
            "day_number": self.day_number,
            "date": self.date.isoformat(),
            "description": self.description,
            "highlights": self.highlights,
            "activities": json.loads(self.activities) if self.activities else [],
            "transport": json.loads(self.transport) if self.transport else [],
            "accommodation": self.accommodation,
        }


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    leg_id = Column(Integer, ForeignKey("legs.id"), nullable=True)
    trip_day_id = Column(Integer, ForeignKey("trip_days.id"), nullable=True)
    category = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(Text, default="CNY")
    description = Column(Text)
    date = Column(Date, nullable=False)

    trip = relationship("Trip", back_populates="expenses")
    leg = relationship("Leg", back_populates="expenses")
    trip_day = relationship("TripDay", back_populates="expenses")

    def to_dict(self):
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "leg_id": self.leg_id,
            "trip_day_id": self.trip_day_id,
            "category": self.category,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "date": self.date.isoformat(),
        }
```

- **Step 5: Create minimal app.py**

```
backend/app.py
```

```python
from flask import Flask
from flask_cors import CORS
from database import init_db

app = Flask(__name__)
CORS(app)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
```

- **Step 6: Create empty package inits**

```
backend/routes/__init__.py
backend/services/__init__.py
```

Both files are empty.

- **Step 7: Write model tests**

```
backend/tests/test_models.py
```

```python
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
```

- **Step 8: Run model tests**

Run: `cd backend && python3 -m pytest tests/test_models.py -v`
Expected: 4 tests PASS

- **Step 9: Verify server starts**

Run: `cd backend && python3 app.py &`
Run: `curl http://localhost:5001/api/health`
Expected: `{"status":"ok"}`

- **Step 10: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold with Trip/Leg/TripDay/Expense models"
```

---

## Task 2: Trip CRUD API

**Files:**

- Create: `backend/routes/trips.py`
- Modify: `backend/app.py` (register blueprint)
- Create: `backend/tests/test_trips.py`
- **Step 1: Create routes/trips.py**

```
backend/routes/trips.py
```

```python
import json
from datetime import date
from flask import Blueprint, request, jsonify
from database import get_session
from models import Trip, Leg, TripDay, Expense

trips_bp = Blueprint("trips", __name__)


def _parse_date(s):
    return date.fromisoformat(s)


@trips_bp.route("/api/trips", methods=["GET"])
def list_trips():
    session = get_session()
    try:
        q = session.query(Trip)
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
        if not trip:
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
        session.delete(trip)
        session.commit()
        return jsonify({"deleted": trip_id})
    finally:
        session.close()
```

- **Step 2: Register blueprint in app.py**

Replace `backend/app.py`:

```python
from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.trips import trips_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(trips_bp)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
```

- **Step 3: Write trip API tests**

```
backend/tests/test_trips.py
```

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


SAMPLE_TRIP = {
    "title": "Test Trip",
    "start_date": "2024-01-01",
    "end_date": "2024-01-05",
    "traveler_count": 2,
    "status": "completed",
    "legs": [{
        "order_index": 1,
        "city": "Tokyo",
        "country": "Japan",
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "days": [{
            "day_number": 1,
            "date": "2024-01-01",
            "description": "Arrival",
            "activities": ["Shibuya"],
            "transport": ["Flight"],
            "accommodation": "Hotel A"
        }]
    }],
    "expenses": [{
        "category": "交通",
        "amount": 5000,
        "currency": "CNY",
        "description": "Flight",
        "date": "2024-01-01"
    }]
}


def test_create_and_get_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Test Trip"
    assert len(data["legs"]) == 1
    assert len(data["expenses"]) == 1

    resp2 = client.get(f"/api/trips/{data['id']}")
    assert resp2.status_code == 200
    assert resp2.get_json()["legs"][0]["days"][0]["activities"] == ["Shibuya"]


def test_list_trips(client):
    client.post("/api/trips", json=SAMPLE_TRIP)
    resp = client.get("/api/trips")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_list_trips_filter_status(client):
    client.post("/api/trips", json=SAMPLE_TRIP)
    resp = client.get("/api/trips?status=planned")
    assert len(resp.get_json()) == 0
    resp2 = client.get("/api/trips?status=completed")
    assert len(resp2.get_json()) == 1


def test_update_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]
    resp2 = client.put(f"/api/trips/{trip_id}", json={"title": "Updated"})
    assert resp2.status_code == 200
    assert resp2.get_json()["title"] == "Updated"


def test_delete_trip(client):
    resp = client.post("/api/trips", json=SAMPLE_TRIP)
    trip_id = resp.get_json()["id"]
    resp2 = client.delete(f"/api/trips/{trip_id}")
    assert resp2.status_code == 200
    resp3 = client.get(f"/api/trips/{trip_id}")
    assert resp3.status_code == 404


def test_get_nonexistent_trip(client):
    resp = client.get("/api/trips/999")
    assert resp.status_code == 404
```

- **Step 4: Run trip API tests**

Run: `cd backend && python3 -m pytest tests/test_trips.py -v`
Expected: 6 tests PASS

- **Step 5: Commit**

```bash
git add backend/routes/trips.py backend/app.py backend/tests/test_trips.py
git commit -m "feat: trip CRUD API with nested legs/days/expenses"
```

---

## Task 3: Stats + Share API

**Files:**

- Create: `backend/routes/stats.py`
- Create: `backend/routes/share.py`
- Modify: `backend/app.py` (register blueprints)
- Create: `backend/tests/test_stats.py`
- Create: `backend/tests/test_share.py`
- **Step 1: Create routes/stats.py**

```
backend/routes/stats.py
```

```python
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
```

- **Step 2: Create routes/share.py**

```
backend/routes/share.py
```

```python
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
        return jsonify({"revoked": True})
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
```

- **Step 3: Register both blueprints in app.py**

Replace `backend/app.py`:

```python
from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.trips import trips_bp
from routes.stats import stats_bp
from routes.share import share_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(trips_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(share_bp)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
```

- **Step 4: Write stats tests**

```
backend/tests/test_stats.py
```

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine

TRIP = {
    "title": "Myanmar", "start_date": "2019-10-01", "end_date": "2019-10-07",
    "traveler_count": 2, "status": "completed",
    "legs": [{"order_index": 1, "city": "Mandalay", "country": "Myanmar",
              "start_date": "2019-10-01", "end_date": "2019-10-03", "days": []}],
    "expenses": [{"category": "交通", "amount": 3344, "date": "2019-10-01"},
                 {"category": "住宿", "amount": 1346.52, "date": "2019-10-01"}],
}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/api/trips", json=TRIP)
        yield c


def test_overview(client):
    resp = client.get("/api/stats/overview")
    data = resp.get_json()
    assert data["total_trips"] == 1
    assert data["total_countries"] == 1
    assert data["total_expense"] == 4690.52


def test_destinations(client):
    resp = client.get("/api/stats/destinations")
    data = resp.get_json()
    assert data["countries"][0][0] == "Myanmar"


def test_expense_stats(client):
    resp = client.get("/api/stats/expenses")
    data = resp.get_json()
    assert len(data["by_category"]) == 2
    assert len(data["by_trip"]) == 1
```

- **Step 5: Write share tests**

```
backend/tests/test_share.py
```

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import app
from database import Base, engine

TRIP = {
    "title": "Share Test", "start_date": "2024-01-01", "end_date": "2024-01-03",
    "status": "completed", "legs": [], "expenses": [],
}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_share_flow(client):
    resp = client.post("/api/trips", json=TRIP)
    trip_id = resp.get_json()["id"]

    resp2 = client.post(f"/api/trips/{trip_id}/share")
    token = resp2.get_json()["share_token"]
    assert len(token) == 12

    resp3 = client.get(f"/api/share/{token}")
    assert resp3.status_code == 200
    assert resp3.get_json()["title"] == "Share Test"

    client.delete(f"/api/trips/{trip_id}/share")
    resp4 = client.get(f"/api/share/{token}")
    assert resp4.status_code == 404
```

- **Step 6: Run all backend tests**

Run: `cd backend && python3 -m pytest tests/ -v`
Expected: All tests PASS

- **Step 7: Commit**

```bash
git add backend/routes/stats.py backend/routes/share.py backend/app.py backend/tests/
git commit -m "feat: stats aggregation API and share token endpoints"
```

---

## Task 4: AI Parse Service

**Files:**

- Create: `backend/services/ai_parser.py`
- Create: `backend/routes/parse.py`
- Modify: `backend/app.py` (register blueprint)
- **Step 1: Create services/ai_parser.py**

```
backend/services/ai_parser.py
```

```python
import json
import os
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a travel itinerary parser. Extract structured trip data from the user's text.

Return a JSON object with this exact structure:
{
  "trip": {
    "title": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "traveler_count": number,
    "description": "string",
    "status": "completed"
  },
  "legs": [
    {
      "order_index": number,
      "city": "string (Chinese name)",
      "country": "string (Chinese name)",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "days": [
        {
          "day_number": number,
          "date": "YYYY-MM-DD",
          "description": "string",
          "highlights": "string or null",
          "activities": ["string"],
          "transport": ["string with flight/train number and time if available"],
          "accommodation": "string or null"
        }
      ]
    }
  ],
  "expenses": [
    {
      "date": "YYYY-MM-DD",
      "category": "交通|住宿|餐饮|门票|购物|其他",
      "amount": number,
      "currency": "CNY",
      "description": "string"
    }
  ]
}

Rules:
- Extract all dates, cities, activities, transport, accommodation, and expenses you can find.
- If a day spans two cities (transfer day), assign it to the departure city's leg.
- For expenses, record total amounts. Note quantity in the description (e.g. "机票 2人").
- If information is unclear, use "[待确认]" as the value.
- Return ONLY valid JSON, no markdown fences, no explanation."""


def parse_text(text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)
```

- **Step 2: Create routes/parse.py**

```
backend/routes/parse.py
```

```python
import io
from flask import Blueprint, request, jsonify
import pdfplumber
from services.ai_parser import parse_text

parse_bp = Blueprint("parse", __name__)


@parse_bp.route("/api/parse", methods=["POST"])
def parse_trip():
    text = None

    if "file" in request.files:
        file = request.files["file"]
        if file.filename.lower().endswith(".pdf"):
            pdf_bytes = file.read()
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(pages)
        else:
            text = file.read().decode("utf-8")
    elif request.json and "text" in request.json:
        text = request.json["text"]

    if not text or not text.strip():
        return jsonify({"error": "No text or file provided"}), 400

    try:
        result = parse_text(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- **Step 3: Register parse blueprint in app.py**

Add to `backend/app.py` imports and registration:

```python
from routes.parse import parse_bp
# ...
app.register_blueprint(parse_bp)
```

Full `backend/app.py`:

```python
from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.trips import trips_bp
from routes.stats import stats_bp
from routes.share import share_bp
from routes.parse import parse_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(trips_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(share_bp)
app.register_blueprint(parse_bp)


@app.route("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
```

- **Step 4: Verify parse endpoint accepts requests**

Run server, then test with curl (requires `ANTHROPIC_API_KEY` env var):

```bash
curl -X POST http://localhost:5001/api/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "2024年1月1日到1月3日去了东京，住在新宿酒店，去了浅草寺和秋叶原，机票花了5000元"}'
```

Expected: JSON response with structured trip data (or error if no API key).

- **Step 5: Commit**

```bash
git add backend/services/ai_parser.py backend/routes/parse.py backend/app.py
git commit -m "feat: AI parse endpoint with Claude for text/PDF trip extraction"
```

---

## Task 5: Frontend Scaffold + Layout

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/App.css`
- Create: `frontend/src/services/api.js`
- Create: `frontend/src/components/Layout.jsx`
- Create: `frontend/src/components/Layout.css`
- **Step 1: Initialize frontend project**

```bash
cd frontend
npm create vite@latest . -- --template react
```

If the directory already exists, select the appropriate option to scaffold in place.

- **Step 2: Install dependencies**

```bash
cd frontend
npm install antd @ant-design/icons react-router-dom axios recharts
```

- **Step 3: Create vite.config.js**

```
frontend/vite.config.js
```

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
})
```

- **Step 4: Create index.html**

```
frontend/index.html
```

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Soul's Travel</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

- **Step 5: Create src/services/api.js**

```
frontend/src/services/api.js
```

```javascript
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const tripApi = {
  list: (params) => api.get('/trips', { params }).then(r => r.data),
  get: (id) => api.get(`/trips/${id}`).then(r => r.data),
  create: (data) => api.post('/trips', data).then(r => r.data),
  update: (id, data) => api.put(`/trips/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/trips/${id}`).then(r => r.data),
  createShare: (id) => api.post(`/trips/${id}/share`).then(r => r.data),
  revokeShare: (id) => api.delete(`/trips/${id}/share`).then(r => r.data),
}

export const statsApi = {
  overview: () => api.get('/stats/overview').then(r => r.data),
  destinations: () => api.get('/stats/destinations').then(r => r.data),
  expenses: () => api.get('/stats/expenses').then(r => r.data),
}

export const shareApi = {
  get: (token) => api.get(`/share/${token}`).then(r => r.data),
}

export const parseApi = {
  text: (text) => api.post('/parse', { text }).then(r => r.data),
  file: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/parse', form).then(r => r.data)
  },
}

export default api
```

- **Step 6: Create src/components/Layout.jsx**

```
frontend/src/components/Layout.jsx
```

```jsx
import { useLocation, useNavigate } from 'react-router-dom'
import {
  HomeOutlined,
  SendOutlined,
  FieldTimeOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import './Layout.css'

const NAV_ITEMS = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/trips', icon: <SendOutlined />, label: '行程' },
  { key: '/timeline', icon: <FieldTimeOutlined />, label: '时间线' },
  { key: '/stats', icon: <BarChartOutlined />, label: '统计' },
]

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const current = '/' + (location.pathname.split('/')[1] || '')

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="sidebar-logo" onClick={() => navigate('/')}>S</div>
        {NAV_ITEMS.map(item => (
          <div
            key={item.key}
            className={`nav-btn ${current === item.key ? 'active' : ''}`}
            onClick={() => navigate(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </div>
        ))}
      </nav>
      <main className="main-content">{children}</main>
    </div>
  )
}
```

- **Step 7: Create src/components/Layout.css**

```
frontend/src/components/Layout.css
```

```css
.app-shell {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.sidebar {
  width: 72px;
  background: #fff;
  border-right: 1px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
  gap: 8px;
  position: sticky;
  top: 0;
  height: 100vh;
}

.sidebar-logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0099ff, #66ccff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 800;
  font-size: 16px;
  margin-bottom: 20px;
  cursor: pointer;
}

.nav-btn {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  cursor: pointer;
  transition: all 0.15s;
  color: #8e99a4;
  font-size: 10px;
}

.nav-btn:hover { background: #f0f2f5; }

.nav-btn.active {
  background: #e8f4ff;
  color: #0099ff;
}

.nav-icon { font-size: 18px; }
.nav-label { font-size: 10px; }

.main-content {
  flex: 1;
  padding: 28px 32px;
  max-width: 1100px;
}
```

- **Step 8: Create src/App.jsx**

```
frontend/src/App.jsx
```

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<Placeholder name="Share" />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Placeholder name="Home" />} />
              <Route path="/trips" element={<Placeholder name="Trips" />} />
              <Route path="/trips/new" element={<Placeholder name="New Trip" />} />
              <Route path="/trips/:id" element={<Placeholder name="Trip Detail" />} />
              <Route path="/trips/:id/edit" element={<Placeholder name="Edit Trip" />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
```

- **Step 9: Create src/App.css**

```
frontend/src/App.css
```

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
  background: #f5f7fa;
  color: #1a1a2e;
}
```

- **Step 10: Update src/main.jsx**

```
frontend/src/main.jsx
```

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './App.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- **Step 11: Run frontend dev server**

Run: `cd frontend && npm run dev`
Expected: Vite dev server on [http://localhost:3000](http://localhost:3000), sidebar visible, placeholder pages render.

- **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold with Vite, React Router, Layout sidebar"
```

---

## Task 6: Home Page + Trip List + TripCard

**Files:**

- Create: `frontend/src/components/TripCard.jsx`
- Create: `frontend/src/components/TripCard.css`
- Create: `frontend/src/pages/Home.jsx`
- Create: `frontend/src/pages/Home.css`
- Create: `frontend/src/pages/TripList.jsx`
- Create: `frontend/src/pages/TripList.css`
- Modify: `frontend/src/App.jsx` (import real pages)
- **Step 1: Create TripCard component**

```
frontend/src/components/TripCard.jsx
```

```jsx
import { useNavigate } from 'react-router-dom'
import './TripCard.css'

const BG_COLORS = ['bg-green', 'bg-yellow', 'bg-blue', 'bg-pink', 'bg-purple']

export default function TripCard({ trip, index = 0 }) {
  const navigate = useNavigate()
  const bgClass = BG_COLORS[index % BG_COLORS.length]
  const days = Math.max(
    1,
    Math.ceil((new Date(trip.end_date) - new Date(trip.start_date)) / 86400000)
  )
  const legCount = trip.legs ? trip.legs.length : 0
  const cities = trip.legs
    ? trip.legs.map(l => l.city).join(' → ')
    : ''

  return (
    <div className={`trip-card ${bgClass}`} onClick={() => navigate(`/trips/${trip.id}`)}>
      <div className="tc-info">
        <div className="tc-title">{trip.title}</div>
        <div className="tc-meta">
          {trip.start_date} 至 {trip.end_date}  
          <b>{days}天</b>
          {legCount > 0 && <><br />{legCount}个城市 &middot; {cities}</>}
        </div>
        {trip.total_expense > 0 && (
          <div className="tc-cost">¥{trip.total_expense.toLocaleString()}</div>
        )}
      </div>
    </div>
  )
}
```

- **Step 2: Create TripCard.css**

```
frontend/src/components/TripCard.css
```

```css
.trip-card {
  border-radius: 20px;
  padding: 22px 26px;
  display: flex;
  align-items: center;
  gap: 20px;
  cursor: pointer;
  transition: all 0.25s;
}
.trip-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
}
.trip-card.bg-green  { background: linear-gradient(135deg, #e8f7ee, #d4f0df); }
.trip-card.bg-yellow { background: linear-gradient(135deg, #fef6e4, #fdecc8); }
.trip-card.bg-blue   { background: linear-gradient(135deg, #e6f2ff, #cce5ff); }
.trip-card.bg-pink   { background: linear-gradient(135deg, #fde8ef, #fbd0df); }
.trip-card.bg-purple { background: linear-gradient(135deg, #f0e6f6, #e3d0f0); }

.tc-info { flex: 1; }
.tc-title { font-size: 19px; font-weight: 700; margin-bottom: 8px; color: #1a1a2e; }
.tc-meta  { font-size: 12px; color: #8e99a4; line-height: 1.6; }
.tc-meta b { color: #4a5568; font-weight: 600; }
.tc-cost  { font-size: 14px; font-weight: 700; color: #ff9500; margin-top: 6px; }
```

- **Step 3: Create Home page**

```
frontend/src/pages/Home.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { tripApi, statsApi } from '../services/api'
import TripCard from '../components/TripCard'
import './Home.css'

export default function Home() {
  const [trips, setTrips] = useState([])
  const [overview, setOverview] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    tripApi.list().then(setTrips).catch(() => {})
    statsApi.overview().then(setOverview).catch(() => {})
  }, [])

  return (
    <div className="home-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">我的<span className="hl">旅行世界</span></h1>
          <p className="page-sub">记录每一段旅程，让回忆有迹可循</p>
        </div>
        <Button type="primary" shape="round" icon={<PlusOutlined />}
                onClick={() => navigate('/trips/new')}>
          新建行程
        </Button>
      </div>

      {overview && (
        <div className="stat-row">
          <div className="stat-pill"><div className="stat-icon blue">✈️</div><div><div className="stat-val">{overview.total_trips}</div><div className="stat-label">旅行次数</div></div></div>
          <div className="stat-pill"><div className="stat-icon green">🌍</div><div><div className="stat-val">{overview.total_countries}</div><div className="stat-label">去过的国家</div></div></div>
          <div className="stat-pill"><div className="stat-icon orange">📅</div><div><div className="stat-val">{overview.total_days}</div><div className="stat-label">旅行天数</div></div></div>
          <div className="stat-pill"><div className="stat-icon purple">💰</div><div><div className="stat-val">¥{(overview.total_expense/1000).toFixed(0)}K</div><div className="stat-label">总花费</div></div></div>
        </div>
      )}

      <div className="sec-head">
        <h2 className="sec-title">最近行程</h2>
      </div>
      <div className="trip-list">
        {trips.slice(0, 5).map((trip, i) => (
          <TripCard key={trip.id} trip={trip} index={i} />
        ))}
        {trips.length === 0 && (
          <div className="empty-state">还没有行程记录，点击右上角开始创建</div>
        )}
      </div>
    </div>
  )
}
```

- **Step 4: Create Home.css**

```
frontend/src/pages/Home.css
```

```css
.home-page .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 26px; font-weight: 700; letter-spacing: -0.3px; }
.page-title .hl { color: #0099ff; }
.page-sub { font-size: 13px; color: #8e99a4; margin-top: 4px; }

.stat-row { display: flex; gap: 12px; margin-bottom: 24px; }
.stat-pill { flex: 1; background: #fff; border-radius: 16px; padding: 18px 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.stat-icon.blue   { background: #e8f4ff; }
.stat-icon.green  { background: #eafaf0; }
.stat-icon.orange { background: #fff5e6; }
.stat-icon.purple { background: #f5eafa; }
.stat-val   { font-size: 22px; font-weight: 700; }
.stat-label { font-size: 11px; color: #8e99a4; margin-top: 2px; }

.sec-head { margin-bottom: 16px; }
.sec-title { font-size: 17px; font-weight: 600; }

.trip-list { display: flex; flex-direction: column; gap: 14px; }
.empty-state { padding: 60px 0; text-align: center; color: #8e99a4; font-size: 14px; }
```

- **Step 5: Create TripList page**

```
frontend/src/pages/TripList.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input, Segmented } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { tripApi } from '../services/api'
import TripCard from '../components/TripCard'
import './TripList.css'

export default function TripList() {
  const [trips, setTrips] = useState([])
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const params = {}
    if (status) params.status = status
    if (search) params.search = search
    tripApi.list(params).then(setTrips).catch(() => {})
  }, [status, search])

  return (
    <div className="triplist-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">我的<span className="hl">行程</span></h1>
          <p className="page-sub">共 {trips.length} 次旅行</p>
        </div>
        <Button type="primary" shape="round" icon={<PlusOutlined />}
                onClick={() => navigate('/trips/new')}>
          新建行程
        </Button>
      </div>

      <div className="filter-bar">
        <Segmented
          value={status || '全部'}
          onChange={v => setStatus(v === '全部' ? '' : v)}
          options={['全部', 'completed', 'planned']}
        />
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索目的地..."
          style={{ width: 200, borderRadius: 50 }}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <div className="trip-list">
        {trips.map((trip, i) => (
          <TripCard key={trip.id} trip={trip} index={i} />
        ))}
        {trips.length === 0 && (
          <div className="empty-state">没有找到行程</div>
        )}
      </div>
    </div>
  )
}
```

- **Step 6: Create TripList.css**

```
frontend/src/pages/TripList.css
```

```css
.triplist-page .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.filter-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; justify-content: space-between; }
```

- **Step 7: Update App.jsx to use real pages**

```
frontend/src/App.jsx
```

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TripList from './pages/TripList'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<Placeholder name="Share" />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<Placeholder name="New Trip" />} />
              <Route path="/trips/:id" element={<Placeholder name="Trip Detail" />} />
              <Route path="/trips/:id/edit" element={<Placeholder name="Edit Trip" />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
```

- **Step 8: Verify pages render**

Run backend + frontend, visit [http://localhost:3000](http://localhost:3000). Home page should show stat pills and trip cards. Visit /trips to see the trip list with filters.

- **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat: Home page with stats, TripList with PiTravel-style cards"
```

---

## Task 7: Trip Detail + Share View

**Files:**

- Create: `frontend/src/pages/TripDetail.jsx`
- Create: `frontend/src/pages/TripDetail.css`
- Create: `frontend/src/components/ExpenseTable.jsx`
- Create: `frontend/src/pages/ShareView.jsx`
- Modify: `frontend/src/App.jsx`
- **Step 1: Create ExpenseTable component**

```
frontend/src/components/ExpenseTable.jsx
```

```jsx
import './ExpenseTable.css'

const CAT_COLORS = { '交通': '#0099ff', '住宿': '#af52de', '餐饮': '#ff9500', '门票': '#34c759', '购物': '#ff6b8a', '其他': '#8e99a4' }

export default function ExpenseTable({ expenses = [], travelerCount = 1 }) {
  const total = expenses.reduce((s, e) => s + e.amount, 0)
  const byCategory = {}
  expenses.forEach(e => { byCategory[e.category] = (byCategory[e.category] || 0) + e.amount })
  const days = expenses.length > 0
    ? new Set(expenses.map(e => e.date)).size
    : 1

  return (
    <div className="expense-card">
      <h3 className="expense-title">💰 开销总览</h3>
      {Object.entries(byCategory).map(([cat, amt]) => (
        <div key={cat} className="expense-bar-row">
          <span className="expense-bar-label">{cat}</span>
          <div className="expense-bar">
            <div className="expense-bar-fill" style={{ width: `${(amt/total)*100}%`, background: CAT_COLORS[cat] || '#8e99a4' }} />
          </div>
          <span className="expense-bar-val">¥{amt.toLocaleString()}</span>
        </div>
      ))}
      <div className="expense-total">
        <span>合计</span><span>¥{total.toLocaleString()}</span>
      </div>
      <div className="expense-per">
        <span>人均 ¥{Math.round(total / travelerCount).toLocaleString()}</span>
        <span>日均 ¥{Math.round(total / days).toLocaleString()}</span>
      </div>
    </div>
  )
}
```

- **Step 2: Create ExpenseTable.css**

```
frontend/src/components/ExpenseTable.css
```

```css
.expense-card { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.expense-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
.expense-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.expense-bar-label { font-size: 11px; color: #8e99a4; width: 36px; }
.expense-bar { flex: 1; height: 10px; background: #f0f2f5; border-radius: 8px; overflow: hidden; }
.expense-bar-fill { height: 100%; border-radius: 8px; }
.expense-bar-val { font-size: 11px; font-weight: 600; width: 64px; text-align: right; }
.expense-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: 700; padding-top: 12px; margin-top: 8px; border-top: 2px solid #1a1a2e; }
.expense-per { display: flex; justify-content: space-between; font-size: 11px; color: #8e99a4; margin-top: 4px; }
```

- **Step 3: Create TripDetail page**

```
frontend/src/pages/TripDetail.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Tag, message } from 'antd'
import { EditOutlined, ShareAltOutlined } from '@ant-design/icons'
import { tripApi } from '../services/api'
import ExpenseTable from '../components/ExpenseTable'
import './TripDetail.css'

const ITEM_ICONS = { transport: '✈️', spot: '🏛', hotel: '🏨', food: '🍽' }

function DayBlock({ day }) {
  return (
    <div className="day-block">
      <div className="day-anchor">📅 Day {day.day_number} · {day.date}</div>
      <div className="day-items-list">
        {day.transport.map((t, i) => (
          <div key={`t${i}`} className="day-item">
            <div className="item-icon transport">✈️</div>
            <div className="item-text"><div className="item-name">{t}</div></div>
          </div>
        ))}
        {day.activities.map((a, i) => (
          <div key={`a${i}`} className="day-item">
            <div className="item-icon spot">🏛</div>
            <div className="item-text"><div className="item-name">{a}</div></div>
          </div>
        ))}
        {day.accommodation && (
          <div className="day-item">
            <div className="item-icon hotel">🏨</div>
            <div className="item-text"><div className="item-name">{day.accommodation}</div></div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function TripDetail() {
  const { id } = useParams()
  const [trip, setTrip] = useState(null)
  const navigate = useNavigate()

  useEffect(() => { tripApi.get(id).then(setTrip).catch(() => {}) }, [id])

  if (!trip) return <div className="loading">加载中...</div>

  const handleShare = async () => {
    const { share_token } = await tripApi.createShare(trip.id)
    message.success(`分享链接: ${window.location.origin}/share/${share_token}`)
  }

  return (
    <div className="detail-page">
      <div className="detail-hero">
        <h1 className="detail-title">{trip.title}</h1>
        <div className="detail-chips">
          <Tag color="blue">📅 {trip.start_date} ~ {trip.end_date}</Tag>
          <Tag color="green">👥 {trip.traveler_count}人</Tag>
          <Tag color="cyan">{trip.status}</Tag>
        </div>
        <div className="detail-actions">
          <Button type="primary" shape="round" icon={<EditOutlined />}
                  onClick={() => navigate(`/trips/${trip.id}/edit`)}>编辑</Button>
          <Button shape="round" icon={<ShareAltOutlined />} onClick={handleShare}>分享</Button>
        </div>
      </div>

      <div className="detail-body">
        <div className="detail-main">
          {trip.legs && trip.legs.map((leg, i) => (
            <div key={leg.id} className="leg-section card">
              <div className="leg-header">
                <div className="leg-badge">{i + 1}</div>
                <div>
                  <div className="leg-title">{leg.city}</div>
                  <div className="leg-dates">{leg.start_date} ~ {leg.end_date}</div>
                </div>
              </div>
              {leg.days && leg.days.map(day => <DayBlock key={day.id} day={day} />)}
            </div>
          ))}
        </div>

        <div className="detail-sidebar">
          <ExpenseTable expenses={trip.expenses} travelerCount={trip.traveler_count} />
        </div>
      </div>
    </div>
  )
}
```

- **Step 4: Create TripDetail.css**

```
frontend/src/pages/TripDetail.css
```

```css
.detail-hero { background: #fff; border-radius: 16px; padding: 28px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.detail-title { font-size: 24px; font-weight: 700; margin-bottom: 10px; }
.detail-chips { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.detail-actions { display: flex; gap: 8px; }

.detail-body { display: flex; gap: 20px; }
.detail-main { flex: 1; }
.detail-sidebar { width: 280px; flex-shrink: 0; }

.leg-section { margin-bottom: 16px; }
.card { background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.leg-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid #f0f2f5; }
.leg-badge { width: 32px; height: 32px; border-radius: 10px; background: #0099ff; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
.leg-title { font-size: 16px; font-weight: 700; }
.leg-dates { font-size: 11px; color: #8e99a4; }

.day-block { margin-bottom: 20px; }
.day-anchor { display: inline-flex; align-items: center; gap: 6px; padding: 5px 14px; border-radius: 50px; background: #0099ff; color: #fff; font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.day-items-list { display: flex; flex-direction: column; gap: 8px; padding-left: 16px; border-left: 2px solid #e5e8ed; }
.day-item { background: #fff; border-radius: 10px; padding: 12px 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); display: flex; align-items: center; gap: 12px; position: relative; }
.day-item::before { content: ''; position: absolute; left: -23px; top: 50%; transform: translateY(-50%); width: 10px; height: 10px; border-radius: 50%; background: #e8f4ff; border: 2px solid #0099ff; }
.item-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
.item-icon.transport { background: #e8f4ff; }
.item-icon.spot { background: #fff5e6; }
.item-icon.hotel { background: #f5eafa; }
.item-icon.food { background: #eafaf0; }
.item-name { font-size: 13px; font-weight: 600; }

.loading { padding: 60px; text-align: center; color: #8e99a4; }
```

- **Step 5: Create ShareView page**

```
frontend/src/pages/ShareView.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Tag } from 'antd'
import { shareApi } from '../services/api'
import './TripDetail.css'

export default function ShareView() {
  const { token } = useParams()
  const [trip, setTrip] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    shareApi.get(token).then(setTrip).catch(() => setError(true))
  }, [token])

  if (error) return <div style={{ padding: 60, textAlign: 'center' }}>行程不存在或已取消分享</div>
  if (!trip) return <div className="loading">加载中...</div>

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '40px 24px' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ color: '#0099ff', fontWeight: 700, fontSize: 15, marginBottom: 8 }}>Soul's Travel</div>
        <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 12 }}>{trip.title}</h1>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
          <Tag color="blue">📅 {trip.start_date} ~ {trip.end_date}</Tag>
          <Tag color="green">{trip.traveler_count}人</Tag>
        </div>
      </div>

      {trip.legs && trip.legs.map((leg, i) => (
        <div key={leg.id} className="leg-section card" style={{ marginBottom: 14 }}>
          <div className="leg-header">
            <div className="leg-badge">{i + 1}</div>
            <div><div className="leg-title">{leg.city}</div><div className="leg-dates">{leg.start_date} ~ {leg.end_date}</div></div>
          </div>
          {leg.days && leg.days.map(day => (
            <div key={day.id} className="day-block">
              <div className="day-anchor" style={{ fontSize: 12, padding: '4px 12px' }}>Day {day.day_number} · {day.date}</div>
              <div className="day-items-list">
                {day.transport.map((t, j) => (
                  <div key={j} className="day-item"><div className="item-icon transport">✈️</div><div className="item-name">{t}</div></div>
                ))}
                {day.activities.map((a, j) => (
                  <div key={j} className="day-item"><div className="item-icon spot">🏛</div><div className="item-name">{a}</div></div>
                ))}
                {day.accommodation && (
                  <div className="day-item"><div className="item-icon hotel">🏨</div><div className="item-name">{day.accommodation}</div></div>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div style={{ textAlign: 'center', padding: 32, borderTop: '1px solid #e5e8ed', marginTop: 16, color: '#8e99a4', fontSize: 12 }}>
        Soul's Travel &middot; 记录旅行，让回忆有迹可循
      </div>
    </div>
  )
}
```

- **Step 6: Update App.jsx with real pages**

```
frontend/src/App.jsx
```

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TripList from './pages/TripList'
import TripDetail from './pages/TripDetail'
import ShareView from './pages/ShareView'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<ShareView />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<Placeholder name="New Trip" />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/edit" element={<Placeholder name="Edit Trip" />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
```

- **Step 7: Verify trip detail and share pages render**

Start backend + frontend, create a trip via API or seed, then visit `/trips/1` and test sharing flow.

- **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: TripDetail with day timeline and ExpenseTable, ShareView for public access"
```

---

## Task 8: Trip Editor (AI Chat + Form)

**Files:**

- Create: `frontend/src/components/ChatPanel.jsx`
- Create: `frontend/src/components/ChatPanel.css`
- Create: `frontend/src/components/TripForm.jsx`
- Create: `frontend/src/components/TripForm.css`
- Create: `frontend/src/pages/TripEditor.jsx`
- Create: `frontend/src/pages/TripEditor.css`
- Modify: `frontend/src/App.jsx`
- **Step 1: Create ChatPanel component**

```
frontend/src/components/ChatPanel.jsx
```

```jsx
import { useState, useRef } from 'react'
import { Button, Input, Upload } from 'antd'
import { PaperClipOutlined, SendOutlined } from '@ant-design/icons'
import { parseApi } from '../services/api'
import './ChatPanel.css'

export default function ChatPanel({ onParsed }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: '你好！我可以帮你快速创建行程 ✨\n\n📄 上传行程 PDF\n📝 粘贴文字描述\n💬 直接告诉我去了哪里' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef()

  const addMsg = (role, text) => setMessages(prev => [...prev, { role, text }])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    addMsg('user', text)
    setLoading(true)
    try {
      const result = await parseApi.text(text)
      addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      onParsed(result)
    } catch (e) {
      addMsg('ai', `解析失败: ${e.message}`)
    }
    setLoading(false)
  }

  const handleFile = async (file) => {
    addMsg('user', `📎 已上传: ${file.name}`)
    setLoading(true)
    try {
      const result = await parseApi.file(file)
      addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      onParsed(result)
    } catch (e) {
      addMsg('ai', `解析失败: ${e.message}`)
    }
    setLoading(false)
    return false
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="ai-avatar">🤖</span>
        <div>
          <div className="ai-name">AI 行程助手</div>
          <div className="ai-tag">Claude</div>
        </div>
      </div>
      <div className="chat-body">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {loading && <div className="msg ai"><div className="bubble typing">解析中...</div></div>}
      </div>
      <div className="chat-input-area">
        <Upload beforeUpload={handleFile} showUploadList={false} accept=".pdf,.txt">
          <Button icon={<PaperClipOutlined />} shape="circle" />
        </Upload>
        <Input
          value={input}
          onChange={e => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入修改指令或补充信息..."
          disabled={loading}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend}
                loading={loading} shape="circle" />
      </div>
    </div>
  )
}
```

- **Step 2: Create ChatPanel.css**

```
frontend/src/components/ChatPanel.css
```

```css
.chat-panel { display: flex; flex-direction: column; height: 100%; background: #fafafa; }
.chat-header { padding: 16px 20px; border-bottom: 1px solid #f0f2f5; display: flex; align-items: center; gap: 10px; background: #fff; }
.ai-avatar { width: 32px; height: 32px; border-radius: 10px; background: linear-gradient(135deg, #0099ff, #66ccff); display: flex; align-items: center; justify-content: center; font-size: 16px; }
.ai-name { font-weight: 600; font-size: 14px; }
.ai-tag { font-size: 10px; color: #8e99a4; }

.chat-body { flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 88%; }
.msg.ai { align-self: flex-start; }
.msg.user { align-self: flex-end; }
.bubble { padding: 12px 16px; border-radius: 16px; font-size: 13px; line-height: 1.65; white-space: pre-wrap; }
.msg.ai .bubble { background: #f0f2f5; border-bottom-left-radius: 4px; }
.msg.user .bubble { background: #0099ff; color: #fff; border-bottom-right-radius: 4px; }
.typing { color: #8e99a4; font-style: italic; }

.chat-input-area { padding: 12px 16px; border-top: 1px solid #f0f2f5; display: flex; gap: 8px; align-items: center; background: #fff; }
.chat-input-area .ant-input { border-radius: 12px; }
```

- **Step 3: Create TripForm component**

```
frontend/src/components/TripForm.jsx
```

```jsx
import { useState, useEffect, useCallback } from 'react'
import { Input, DatePicker, InputNumber, Button, Collapse } from 'antd'
import dayjs from 'dayjs'
import './TripForm.css'

export default function TripForm({ data, onSave }) {
  const [form, setForm] = useState({ title: '', start_date: '', end_date: '', traveler_count: 1, description: '', legs: [], expenses: [] })
  const [dirty, setDirty] = useState(new Set())

  useEffect(() => {
    if (data) {
      setForm(prev => {
        const next = { ...prev }
        Object.keys(data.trip || {}).forEach(k => {
          if (!dirty.has(k)) next[k] = data.trip[k]
        })
        if (!dirty.has('legs') && data.legs) next.legs = data.legs
        if (!dirty.has('expenses') && data.expenses) next.expenses = data.expenses
        return next
      })
    }
  }, [data])

  const setField = useCallback((key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setDirty(prev => new Set(prev).add(key))
  }, [])

  const handleSave = () => {
    const payload = {
      title: form.title,
      start_date: form.start_date,
      end_date: form.end_date,
      traveler_count: form.traveler_count,
      description: form.description,
      status: 'completed',
      legs: form.legs,
      expenses: form.expenses,
    }
    onSave(payload)
  }

  const legItems = (form.legs || []).map((leg, li) => ({
    key: li,
    label: `🏙️ ${leg.city || `站点 ${li+1}`} (${leg.start_date} ~ ${leg.end_date})`,
    children: (
      <div>
        {(leg.days || []).map((day, di) => (
          <div key={di} className="day-form-block">
            <div className="day-form-label">Day {day.day_number} · {day.date}</div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">活动</label>
                <Input value={(day.activities || []).join(', ')} readOnly className="f-input ai-fill" />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">交通</label>
                <Input value={(day.transport || []).join(', ')} readOnly className="f-input ai-fill" />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">住宿</label>
                <Input value={day.accommodation || ''} readOnly className="f-input ai-fill" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }))

  return (
    <div className="trip-form">
      <div className="form-header">
        <h3>行程表单</h3>
        <Button type="primary" shape="round" onClick={handleSave}>💾 保存行程</Button>
      </div>

      <div className="form-block">
        <h4>📋 基本信息</h4>
        <div className="f-row">
          <div className="f-group">
            <label className="f-label">标题</label>
            <Input value={form.title} onChange={e => setField('title', e.target.value)} />
          </div>
          <div className="f-group" style={{ flex: '0 0 100px' }}>
            <label className="f-label">人数</label>
            <InputNumber min={1} value={form.traveler_count} onChange={v => setField('traveler_count', v)} style={{ width: '100%' }} />
          </div>
        </div>
        <div className="f-row">
          <div className="f-group">
            <label className="f-label">开始</label>
            <DatePicker value={form.start_date ? dayjs(form.start_date) : null}
                        onChange={(d, s) => setField('start_date', s)} style={{ width: '100%' }} />
          </div>
          <div className="f-group">
            <label className="f-label">结束</label>
            <DatePicker value={form.end_date ? dayjs(form.end_date) : null}
                        onChange={(d, s) => setField('end_date', s)} style={{ width: '100%' }} />
          </div>
        </div>
      </div>

      {legItems.length > 0 && (
        <div className="form-block">
          <h4>🏙️ 城市站点</h4>
          <Collapse items={legItems} defaultActiveKey={[0]} />
        </div>
      )}
    </div>
  )
}
```

- **Step 4: Create TripForm.css**

```
frontend/src/components/TripForm.css
```

```css
.trip-form { padding: 4px; }
.form-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.form-header h3 { font-size: 17px; font-weight: 700; }
.form-block { background: #fff; border-radius: 16px; padding: 18px 20px; margin-bottom: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.form-block h4 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.f-row { display: flex; gap: 12px; margin-bottom: 10px; }
.f-group { flex: 1; }
.f-label { font-size: 11px; color: #8e99a4; margin-bottom: 3px; display: block; }
.f-input.ai-fill { background: #f0f9ff; border-color: #b3deff; }
.day-form-block { background: #e8f4ff; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }
.day-form-label { font-size: 12px; font-weight: 600; color: #0099ff; margin-bottom: 8px; }
```

- **Step 5: Create TripEditor page**

```
frontend/src/pages/TripEditor.jsx
```

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import ChatPanel from '../components/ChatPanel'
import TripForm from '../components/TripForm'
import { tripApi } from '../services/api'
import './TripEditor.css'

export default function TripEditor() {
  const [parsedData, setParsedData] = useState(null)
  const navigate = useNavigate()

  const handleSave = async (payload) => {
    try {
      const created = await tripApi.create(payload)
      message.success('行程已保存')
      navigate(`/trips/${created.id}`)
    } catch (e) {
      message.error('保存失败: ' + (e.response?.data?.error || e.message))
    }
  }

  return (
    <div className="editor-layout">
      <div className="editor-chat">
        <ChatPanel onParsed={setParsedData} />
      </div>
      <div className="editor-form">
        <TripForm data={parsedData} onSave={handleSave} />
      </div>
    </div>
  )
}
```

- **Step 6: Create TripEditor.css**

```
frontend/src/pages/TripEditor.css
```

```css
.editor-layout { display: flex; height: calc(100vh - 56px); margin: -28px -32px; }
.editor-chat { width: 400px; border-right: 1px solid #f0f2f5; }
.editor-form { flex: 1; overflow-y: auto; padding: 24px 28px; background: #f5f7fa; }
```

- **Step 7: Update App.jsx**

```
frontend/src/App.jsx
```

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TripList from './pages/TripList'
import TripDetail from './pages/TripDetail'
import TripEditor from './pages/TripEditor'
import ShareView from './pages/ShareView'

function Placeholder({ name }) {
  return <div style={{ padding: 40, fontSize: 20, color: '#8e99a4' }}>{name} - Coming Soon</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<ShareView />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<TripEditor />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/edit" element={<TripEditor />} />
              <Route path="/timeline" element={<Placeholder name="Timeline" />} />
              <Route path="/stats" element={<Placeholder name="Stats" />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
```

- **Step 8: Verify editor renders with chat + form split**

Visit [http://localhost:3000/trips/new](http://localhost:3000/trips/new). Left panel should show AI chat, right panel shows form. Upload or type to test AI parsing.

- **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat: TripEditor with AI ChatPanel and structured TripForm (dirty flag)"
```

---

## Task 9: Timeline + Stats Pages

**Files:**

- Create: `frontend/src/components/TimelineNode.jsx`
- Create: `frontend/src/components/StatsChart.jsx`
- Create: `frontend/src/pages/Timeline.jsx`
- Create: `frontend/src/pages/Timeline.css`
- Create: `frontend/src/pages/Stats.jsx`
- Create: `frontend/src/pages/Stats.css`
- Modify: `frontend/src/App.jsx`
- **Step 1: Create TimelineNode component**

```
frontend/src/components/TimelineNode.jsx
```

```jsx
import { useNavigate } from 'react-router-dom'

export default function TimelineNode({ trip }) {
  const navigate = useNavigate()
  const cities = trip.legs ? trip.legs.map(l => l.city).join(' → ') : ''

  return (
    <div className="tl-node" onClick={() => navigate(`/trips/${trip.id}`)}>
      <div className="tl-card">
        <div className="tl-card-title">{trip.title}</div>
        {cities && <div className="tl-card-route">{cities}</div>}
        <div className="tl-card-meta">
          <span>{trip.start_date} ~ {trip.end_date}</span>
          <span>{trip.traveler_count}人</span>
        </div>
      </div>
    </div>
  )
}
```

- **Step 2: Create Timeline page**

```
frontend/src/pages/Timeline.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { tripApi } from '../services/api'
import TimelineNode from '../components/TimelineNode'
import './Timeline.css'

export default function Timeline() {
  const [trips, setTrips] = useState([])

  useEffect(() => { tripApi.list().then(setTrips).catch(() => {}) }, [])

  const grouped = {}
  trips.forEach(t => {
    const year = t.start_date.slice(0, 4)
    if (!grouped[year]) grouped[year] = []
    grouped[year].push(t)
  })
  const years = Object.keys(grouped).sort((a, b) => b - a)

  return (
    <div className="timeline-page">
      <h1 className="page-title">旅行<span className="hl">时间线</span></h1>
      <p className="page-sub">{trips.length} 次旅行的足迹</p>

      {years.map(year => (
        <div key={year}>
          <div className="tl-year">{year} <span className="yr-badge">{grouped[year].length}次</span></div>
          <div className="tl-track">
            {grouped[year].map(trip => <TimelineNode key={trip.id} trip={trip} />)}
          </div>
        </div>
      ))}

      {trips.length === 0 && <div className="empty-state">还没有行程记录</div>}
    </div>
  )
}
```

- **Step 3: Create Timeline.css**

```
frontend/src/pages/Timeline.css
```

```css
.timeline-page { max-width: 760px; }
.tl-year { font-size: 28px; font-weight: 800; margin: 28px 0 14px; }
.tl-year:first-of-type { margin-top: 24px; }
.yr-badge { font-size: 13px; font-weight: 600; color: #0099ff; background: #e8f4ff; padding: 3px 10px; border-radius: 50px; margin-left: 8px; vertical-align: middle; }

.tl-track { padding-left: 28px; position: relative; }
.tl-track::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: #e5e8ed; }

.tl-node { position: relative; margin-bottom: 16px; cursor: pointer; }
.tl-node::before { content: ''; position: absolute; left: -20px; top: 18px; width: 12px; height: 12px; border-radius: 50%; background: #fff; border: 3px solid #0099ff; z-index: 1; }

.tl-card { background: #fff; border-radius: 16px; padding: 18px 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); transition: all 0.2s; }
.tl-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
.tl-card-title { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.tl-card-route { font-size: 12px; color: #0099ff; font-weight: 500; margin-bottom: 6px; }
.tl-card-meta { display: flex; gap: 16px; font-size: 11px; color: #8e99a4; }
```

- **Step 4: Create StatsChart components**

```
frontend/src/components/StatsChart.jsx
```

```jsx
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, Area, AreaChart, ResponsiveContainer } from 'recharts'

const COLORS = ['#0099ff', '#af52de', '#ff9500', '#34c759', '#ff6b8a', '#8e99a4']

export function CategoryPie({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={data} dataKey="total" nameKey="category" cx="50%" cy="50%"
             outerRadius={80} label={({ category, percent }) => `${category} ${(percent * 100).toFixed(0)}%`}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function TripExpenseBar({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <XAxis dataKey="title" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="total" fill="#0099ff" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PerDayTrend({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data}>
        <XAxis dataKey="title" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <defs>
          <linearGradient id="colorPpd" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0099ff" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#0099ff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="per_person_per_day" stroke="#0099ff" fill="url(#colorPpd)" strokeWidth={2.5} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function DestinationRank({ data, label }) {
  const max = data.length > 0 ? data[0][1] : 1
  return (
    <div>
      {data.slice(0, 8).map(([name, count], i) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #f0f2f5' }}>
          <span style={{ width: 22, height: 22, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                         fontSize: 11, fontWeight: 700,
                         background: i < 3 ? ['#fff5e6','#e8f4ff','#f5eafa'][i] : '#f0f2f5',
                         color: i < 3 ? ['#ff9500','#0099ff','#af52de'][i] : '#8e99a4' }}>
            {i + 1}
          </span>
          <span style={{ width: 64, fontSize: 13, fontWeight: 500 }}>{name}</span>
          <div style={{ flex: 1, height: 8, background: '#f0f2f5', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ width: `${(count / max) * 100}%`, height: '100%', borderRadius: 6, background: 'linear-gradient(90deg, #0099ff, #66ccff)' }} />
          </div>
          <span style={{ width: 32, textAlign: 'right', fontSize: 11, color: '#8e99a4' }}>{count}次</span>
        </div>
      ))}
    </div>
  )
}
```

- **Step 5: Create Stats page**

```
frontend/src/pages/Stats.jsx
```

```jsx
import { useEffect, useState } from 'react'
import { statsApi } from '../services/api'
import { CategoryPie, TripExpenseBar, PerDayTrend, DestinationRank } from '../components/StatsChart'
import './Stats.css'

export default function Stats() {
  const [overview, setOverview] = useState(null)
  const [destinations, setDestinations] = useState(null)
  const [expenses, setExpenses] = useState(null)

  useEffect(() => {
    statsApi.overview().then(setOverview).catch(() => {})
    statsApi.destinations().then(setDestinations).catch(() => {})
    statsApi.expenses().then(setExpenses).catch(() => {})
  }, [])

  return (
    <div className="stats-page">
      <h1 className="page-title">生涯<span className="hl">统计</span></h1>
      <p className="page-sub">你的旅行数据全览</p>

      {overview && (
        <div className="stats-overview">
          <div className="stats-num"><div className="n">{overview.total_trips}</div><div className="l">旅行次数</div></div>
          <div className="stats-num"><div className="n">{overview.total_days}</div><div className="l">总天数</div></div>
          <div className="stats-num"><div className="n">{overview.total_countries}</div><div className="l">国家</div></div>
          <div className="stats-num"><div className="n">{overview.total_cities}</div><div className="l">城市</div></div>
          <div className="stats-num"><div className="n">¥{(overview.total_expense/1000).toFixed(0)}K</div><div className="l">总花费</div></div>
          <div className="stats-num"><div className="n">¥{(overview.avg_expense_per_trip/1000).toFixed(1)}K</div><div className="l">次均花费</div></div>
        </div>
      )}

      <div className="chart-row">
        {destinations && (
          <div className="chart-card">
            <h3 className="chart-card-title">🌍 国家访问排名</h3>
            <DestinationRank data={destinations.countries} label="国家" />
          </div>
        )}
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">💰 开销类别占比</h3>
            <CategoryPie data={expenses.by_category} />
          </div>
        )}
      </div>

      <div className="chart-row">
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">📊 各旅行花费对比</h3>
            <TripExpenseBar data={expenses.by_trip} />
          </div>
        )}
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">📈 人均日消费趋势</h3>
            <PerDayTrend data={expenses.per_day_trend} />
          </div>
        )}
      </div>
    </div>
  )
}
```

- **Step 6: Create Stats.css**

```
frontend/src/pages/Stats.css
```

```css
.stats-overview { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 24px; }
.stats-num { background: #fff; border-radius: 16px; padding: 16px 12px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.stats-num .n { font-size: 24px; font-weight: 800; }
.stats-num .l { font-size: 10px; color: #8e99a4; margin-top: 4px; }

.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-card { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.chart-card-title { font-size: 14px; font-weight: 600; margin-bottom: 16px; }
```

- **Step 7: Update App.jsx with Timeline and Stats**

```
frontend/src/App.jsx
```

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TripList from './pages/TripList'
import TripDetail from './pages/TripDetail'
import TripEditor from './pages/TripEditor'
import Timeline from './pages/Timeline'
import Stats from './pages/Stats'
import ShareView from './pages/ShareView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/share/:token" element={<ShareView />} />
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<TripEditor />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/edit" element={<TripEditor />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/stats" element={<Stats />} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}
```

- **Step 8: Verify all pages render**

Visit /timeline and /stats. Timeline should show trips grouped by year. Stats should show overview numbers and charts (once data exists).

- **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat: Timeline page with year groups, Stats dashboard with Recharts"
```

---

## Task 10: Seed Script + README

**Files:**

- Create: `backend/seed.py`
- Create: `README.md`
- **Step 1: Create seed.py**

```
backend/seed.py
```

```python
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

    session.commit()
    session.close()
    print(f"Seeded: {trip.title} ({len(data['legs'])} legs, {len(data['expenses'])} expenses)")


if __name__ == "__main__":
    seed()
```

- **Step 2: Run seed**

Run: `cd backend && python3 seed.py`
Expected: `Seeded: SouL的缅甸行程 (3 legs, 7 expenses)`

- **Step 3: Create README.md**

```
README.md
```

```markdown
# Soul's Travel

个人旅游经历记录与分析工具。AI 辅助录入旅行数据，多维度统计分析，优化未来旅行计划。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Claude API Key (用于 AI 解析功能)

### 后端

```bash
cd backend
pip3 install -r requirements.txt
python3 seed.py          # 导入样例数据（缅甸行程）
python3 app.py           # 启动后端 → http://localhost:5001
```

### 前端

```bash
cd frontend
npm install
npm run dev              # 启动前端 → http://localhost:3000
```

### 环境变量

```bash
export ANTHROPIC_API_KEY="your-api-key"   # AI 解析功能需要
```

## 功能

- **行程管理** — AI 辅助录入（上传 PDF / 自然语言对话），结构化编辑
- **生涯统计** — 目的地排名、开销占比、消费趋势
- **旅行时间线** — 按年分组的垂直时间轴
- **分享** — 生成公开链接让朋友查看行程

## 技术栈

- 前端: React 18 + Vite + Ant Design + Recharts
- 后端: Flask + SQLAlchemy + SQLite
- AI: Claude API (Anthropic)

详细设计见 [DESIGN.md](DESIGN.md)。

```

- [ ] **Step 4: Verify full flow end-to-end**

1. Start backend: `cd backend && python3 app.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Home page shows Myanmar trip stats and card
5. Click trip card → detail page with day timeline and expenses
6. Visit /trips/new → AI editor
7. Visit /timeline → year-grouped timeline
8. Visit /stats → charts and rankings

- [ ] **Step 5: Commit**

```bash
git add backend/seed.py README.md
git commit -m "feat: seed script for sample data, README with setup instructions"
```

