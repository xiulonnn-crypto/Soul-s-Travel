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
    from models import Trip, Leg, TripDay, Expense, TripEvaluation, UserProfile  # noqa: F401
    Base.metadata.create_all(engine, checkfirst=True)
    _migrate_add_is_deleted()


def _migrate_add_is_deleted():
    """Add is_deleted column to trips table if it doesn't exist."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    columns = [c["name"] for c in insp.get_columns("trips")]
    if "is_deleted" not in columns:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE trips ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"
            ))
