import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Text, Float, Date, DateTime, ForeignKey, Boolean
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
    is_deleted = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    legs = relationship("Leg", back_populates="trip", cascade="all, delete-orphan",
                        order_by="Leg.order_index")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")
    evaluation = relationship("TripEvaluation", uselist=False, back_populates="trip")

    def to_dict(self, include_legs=False, include_expenses=False, include_summary=False):
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
        if include_summary:
            legs = self.legs
            seen = []
            for leg in legs:
                label = leg.city if leg.country == "中国" else leg.country
                if label and label != "[待确认]" and label not in seen:
                    seen.append(label)
            d["destination_label"] = " · ".join(seen) if seen else ""
            d["leg_count"] = len(legs)
            d["total_expense"] = sum(e.amount for e in self.expenses)
            d["evaluation_score"] = self.evaluation.overall_score if self.evaluation else None
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


class TripEvaluation(Base):
    __tablename__ = "trip_evaluations"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, unique=True)
    overall_score = Column(Integer, nullable=False)
    evaluation_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trip = relationship("Trip", back_populates="evaluation")

    def to_dict(self):
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "overall_score": self.overall_score,
            "evaluation_data": json.loads(self.evaluation_data) if self.evaluation_data else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    household_income = Column(Float, default=1600000)
    annual_travel_budget = Column(Float, default=100000)
    family_description = Column(Text, default="夫妻两人")
    visited_countries_cities = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        visited = {}
        if self.visited_countries_cities:
            try:
                visited = json.loads(self.visited_countries_cities)
            except json.JSONDecodeError:
                visited = {}
        return {
            "id": self.id,
            "household_income": self.household_income,
            "annual_travel_budget": self.annual_travel_budget,
            "family_description": self.family_description,
            "visited_countries_cities": visited,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
