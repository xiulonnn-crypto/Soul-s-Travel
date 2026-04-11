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
    from models import Trip, Leg, TripDay, Expense, TripEvaluation  # noqa: F401
    Base.metadata.create_all(engine)
