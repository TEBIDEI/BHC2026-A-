import uuid
from datetime import datetime, timezone

from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geography
from werkzeug.security import check_password_hash, generate_password_hash

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

AREA_LEVELS = {
    "punkt": "Punkt",
    "miasto": "Miasto",
    "powiat": "Powiat",
    "region": "Region",
    "panstwo": "Państwo",
}

FACT_PRESETS = {
    "stroj": ["Nazwa", "Region", "Okazja", "Charakterystyczne elementy", "Materiały"],
    "kuchnia": ["Główne składniki", "Kiedy się je", "Pochodzenie nazwy"],
    "jezyk": ["Język", "Pismo", "Liczba mówiących", "Status"],
    "architektura": ["Styl", "Czas powstania", "Materiał", "Ciekawostka"],
    "muzyka": ["Nazwa", "Instrumenty", "Okazja"],
    "zwyczaje": ["Nazwa", "Kiedy", "Region"],
    "inne": [],
}


def _now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), nullable=False)
    username_key = db.Column(db.String(32), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


set_questions = db.Table(
    "set_questions",
    db.Column("set_id", db.Integer, db.ForeignKey("question_sets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("question_id", db.Integer, db.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
)


class QuestionSet(db.Model):
    __tablename__ = "question_sets"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    questions = db.relationship(
        "Question", secondary=set_questions, back_populates="sets", order_by="Question.id"
    )

    @property
    def active_questions(self):
        return [q for q in self.questions if q.active]

    @property
    def cover(self):
        qs = self.active_questions
        return qs[0].image_src if qs else None


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(32), nullable=False, default="inne", index=True)
    location_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    facts = db.Column(db.JSON, nullable=False, default=list)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    area_level = db.Column(db.String(16), nullable=False, default="punkt")
    area = db.Column(Geography("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=True)
    image_filename = db.Column(db.String(255))
    image_url = db.Column(db.String(1000))
    image_credit = db.Column(db.String(500))
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    sets = db.relationship("QuestionSet", secondary=set_questions, back_populates="questions")

    @property
    def category_label(self):
        return CATEGORIES.get(self.category, self.category)

    @property
    def level_label(self):
        return AREA_LEVELS.get(self.area_level, self.area_level)

    @property
    def image_src(self):
        if self.image_filename:
            return url_for("static", filename=f"uploads/{self.image_filename}")
        return self.image_url

    def public_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "category_label": self.category_label,
            "image": self.image_src,
        }

    def answer_dict(self):
        return {
            "title": self.title,
            "category": self.category,
            "location_name": self.location_name,
            "description": self.description,
            "facts": [f for f in (self.facts or []) if f.get("label") and f.get("value")],
            "level": self.area_level if self.area is not None else "punkt",
            "level_label": self.level_label if self.area is not None else AREA_LEVELS["punkt"],
            "lat": self.lat,
            "lng": self.lng,
            "image": self.image_src,
            "image_credit": self.image_credit,
        }


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_ids = db.Column(db.JSON, nullable=False)
    current_round = db.Column(db.Integer, nullable=False, default=0)
    total_score = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    set_id = db.Column(db.Integer, db.ForeignKey("question_sets.id", ondelete="SET NULL"), index=True)
    ranked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    finished_at = db.Column(db.DateTime(timezone=True), index=True)

    user = db.relationship("User")
    question_set = db.relationship("QuestionSet")
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
