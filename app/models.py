import uuid
from datetime import datetime, timezone

from flask import url_for
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

CATEGORIES = {
    "kuchnia": "Kuchnia",
    "stroj": "Strój",
    "jezyk": "Język",
    "architektura": "Architektura",
    "muzyka": "Muzyka i taniec",
    "zwyczaje": "Zwyczaje",
    "inne": "Inne",
}


def _now():
    return datetime.now(timezone.utc)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(32), nullable=False, default="inne", index=True)
    location_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(255))
    image_url = db.Column(db.String(1000))
    image_credit = db.Column(db.String(500))
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    @property
    def category_label(self):
        return CATEGORIES.get(self.category, self.category)

    @property
    def image_src(self):
        if self.image_filename:
            return url_for("static", filename=f"uploads/{self.image_filename}")
        return self.image_url

    def public_dict(self):
        """Dane widoczne dla gracza PRZED zgadnięciem — bez odpowiedzi."""
        return {
            "id": self.id,
            "category": self.category,
            "category_label": self.category_label,
            "image": self.image_src,
        }

    def answer_dict(self):
        return {
            "title": self.title,
            "location_name": self.location_name,
            "description": self.description,
            "lat": self.lat,
            "lng": self.lng,
            "image": self.image_src,
            "image_credit": self.image_credit,
        }


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_ids = db.Column(db.JSON, nullable=False)
    current_round = db.Column(db.Integer, nullable=False, default=0)  # 0-based
    total_score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    guesses = db.relationship(
        "Guess", backref="game", order_by="Guess.round", cascade="all, delete-orphan"
    )

    @property
    def rounds(self):
        return len(self.question_ids)

    @property
    def finished(self):
        return self.current_round >= self.rounds


class Guess(db.Model):
    __tablename__ = "guesses"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(36), db.ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="SET NULL"))
    round = db.Column(db.Integer, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    question = db.relationship("Question", passive_deletes=True)
