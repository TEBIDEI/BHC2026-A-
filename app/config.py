import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    APP_NAME = "CultureGuessr"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg2://geo:geo@localhost:5433/cultureguessr"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    UPLOAD_DIR = BASE_DIR / "static" / "uploads"
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    MAX_IMAGE_SIDE = 1600

    ROUNDS_PER_GAME = int(os.environ.get("ROUNDS_PER_GAME", 10))
    MAX_ROUND_SCORE = 5000
    # Im większa skala, tym łagodniej spadają punkty z odległością.
    SCORE_SCALE_KM = float(os.environ.get("SCORE_SCALE_KM", 750))
    # Kliknięcie bliżej niż tyle km = pełne 5000 pkt.
    PERFECT_RADIUS_KM = float(os.environ.get("PERFECT_RADIUS_KM", 15))

    # Puste = panel bez hasła (wygodne lokalnie).
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
