import random

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func

from .models import CATEGORIES, Game, Guess, Question, db
from .scoring import distance_km, score_from_distance

bp = Blueprint("api", __name__, url_prefix="/api")


def error(message, status=400):
    return jsonify({"error": message}), status


def game_state(game):
    state = {
        "game_id": game.id,
        "rounds": game.rounds,
        "round": min(game.current_round + 1, game.rounds),
        "total_score": game.total_score,
        "max_score": game.rounds * current_app.config["MAX_ROUND_SCORE"],
        "finished": game.finished,
    }
    if game.finished:
        state["summary"] = [
            {
                "round": g.round,
                "guess": {"lat": g.lat, "lng": g.lng},
                "distance_km": round(g.distance_km, 1),
                "score": g.score,
                "answer": g.question.answer_dict() if g.question else None,
            }
            for g in game.guesses
        ]
    else:
        question = db.session.get(Question, game.question_ids[game.current_round])
        state["question"] = question.public_dict() if question else None
    return state


@bp.get("/categories")
def categories():
    counts = dict(
        db.session.query(Question.category, func.count(Question.id))
        .filter(Question.active.is_(True))
        .group_by(Question.category)
        .all()
    )
    return jsonify(
        {
            "total": sum(counts.values()),
            "categories": [
                {"key": key, "label": label, "count": counts.get(key, 0)}
                for key, label in CATEGORIES.items()
            ],
        }
    )


@bp.post("/games")
def create_game():
    data = request.get_json(silent=True) or {}
    rounds = data.get("rounds") or current_app.config["ROUNDS_PER_GAME"]
    try:
        rounds = max(1, min(int(rounds), 50))
    except (TypeError, ValueError):
        return error("Nieprawidłowa liczba rund.")

    query = db.session.query(Question.id).filter(Question.active.is_(True))
    if data.get("category"):
        query = query.filter(Question.category == data["category"])
    ids = [row.id for row in query]
    if not ids:
        return error("Brak pytań w tej kategorii — dodaj je w panelu /admin.", 404)

    game = Game(question_ids=random.sample(ids, min(rounds, len(ids))))
    db.session.add(game)
    db.session.commit()
    return jsonify(game_state(game)), 201


@bp.get("/games/<game_id>")
def get_game(game_id):
    game = db.session.get(Game, game_id)
    if not game:
        return error("Nie znaleziono gry.", 404)
    return jsonify(game_state(game))


@bp.post("/games/<game_id>/guess")
def guess(game_id):
    game = db.session.query(Game).filter_by(id=game_id).with_for_update().first()
    if not game:
        return error("Nie znaleziono gry.", 404)
    if game.finished:
        return error("Gra jest już zakończona.", 409)

    data = request.get_json(silent=True) or {}
    if "round" in data and data["round"] != game.current_round + 1:
        return error("Ta runda została już rozegrana.", 409)
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
    except (KeyError, TypeError, ValueError):
        return error("Brak współrzędnych.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return error("Współrzędne poza zakresem.")

    question = db.session.get(Question, game.question_ids[game.current_round])
    if not question:
        return error("To pytanie zostało usunięte.", 410)

    cfg = current_app.config
    dist = distance_km(question, lat, lng)
    score = score_from_distance(
        dist, cfg["MAX_ROUND_SCORE"], cfg["SCORE_SCALE_KM"], cfg["PERFECT_RADIUS_KM"]
    )
    db.session.add(
        Guess(
            game_id=game.id,
            question_id=question.id,
            round=game.current_round + 1,
            lat=lat,
            lng=lng,
            distance_km=dist,
            score=score,
        )
    )
    game.total_score += score
    game.current_round += 1
    db.session.commit()

    return jsonify(
        {
            "round": game.current_round,
            "rounds": game.rounds,
            "distance_km": round(dist, 1),
            "score": score,
            "max_round_score": cfg["MAX_ROUND_SCORE"],
            "total_score": game.total_score,
            "finished": game.finished,
            "answer": question.answer_dict(),
        }
    )
