import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from database import Base


@pytest.fixture(autouse=True)
def isolated_db():
    """Redirect all DB operations to an in-memory SQLite so tests never touch travel.db."""
    _orig_engine = database.engine
    _orig_session = database.Session

    test_engine = create_engine("sqlite:///:memory:")
    database.engine = test_engine
    database.Session = sessionmaker(bind=test_engine)
    Base.metadata.create_all(test_engine)

    yield

    Base.metadata.drop_all(test_engine)
    database.engine = _orig_engine
    database.Session = _orig_session
