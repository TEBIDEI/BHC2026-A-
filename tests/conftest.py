import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app import create_app
from app.config import Config
from app.models import db

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://geo:geo@localhost:5433/cultureguessr_test"
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = TEST_DB_URL
    ADMIN_PASSWORD = ""
    ROUNDS_PER_GAME = 3


def _ensure_database():
    url = make_url(TEST_DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError:
        pytest.skip("Brak Postgresa dla testów. Uruchom `docker compose up -d`.", allow_module_level=True)
    finally:
        admin.dispose()
    with create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


@pytest.fixture(scope="session", autouse=True)
def database():
    _ensure_database()


@pytest.fixture
def make_app():
    def factory(seed=None):
        app = create_app(TestConfig)
        with app.app_context():
            db.drop_all()
            db.create_all()
            if seed:
                seed()
            db.session.commit()
        return app

    return factory
