import random
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request, url_for

from .models import Game, Guess, Question, QuestionSet, db
from .geo import answer_distance, area_geojson
from .ranking import ALL_SLUG, position, week_start
from .scoring import score_from_distance

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
        "ranked": game.ranked,
        "set": {
            "slug": game.question_set.slug if game.question_set else ALL_SLUG,
            "name": game.question_set.name if game.question_set else "Wszystkie pytania",
        },
    }
    if game.finished:
        areas = area_geojson([gs.question_id for gs in game.guesses])
        state["summary"] = [
            {
                "round": gs.round,
                "guess": {"lat": gs.lat, "lng": gs.lng},
                "distance_km": round(gs.distance_km, 1),
                "score": gs.score,
                "answer": {**gs.question.answer_dict(), "area": areas.get(gs.question_id)} if gs.question else None,
            }
            for gs in game.guesses
        ]
        if game.ranked and game.user_id:
            state["ranking"] = ranking_info(game)
    else:
        question = db.session.get(Question, game.question_ids[game.current_round])
        state["question"] = question.public_dict() if question else None
    return state


def ranking_info(game):
    pos_all, best_all = position(game.user_id, game.set_id)
    pos_week, _ = position(game.user_id, game.set_id, week_start())
    slug = game.question_set.slug if game.question_set else ALL_SLUG
    return {
        "position": pos_all,
        "best": best_all,
        "week_position": pos_week,
        "new_best": best_all == game.total_score,
        "url": url_for("ranking.board", slug=slug),
    }


def _active_ids(question_set=None):
    if question_set:
        return [q.id for q in question_set.active_questions]
    return [row.id for row in db.session.query(Question.id).filter(Question.active.is_(True))]


@bp.get("/sets")
def sets():
    items = []
    for s in QuestionSet.query.filter_by(active=True).order_by(QuestionSet.position, QuestionSet.name):
        count = len(s.active_questions)
        if count:
            items.append({"slug": s.slug, "name": s.name, "description": s.description, "count": count, "cover": s.cover})
    items.append({
        "slug": ALL_SLUG,
        "name": "Wszystkie pytania",
        "description": "Mieszanka wszystkiego, co jest w bazie.",
        "count": len(_active_ids()),
        "cover": None,
    })
    return jsonify({"sets": items, "logged_in": g.user is not None,
                    "ranked_rounds": current_app.config["ROUNDS_PER_GAME"]})


@bp.post("/games")
def create_game():
    data = request.get_json(silent=True) or {}
    full = current_app.config["ROUNDS_PER_GAME"]
    try:
        rounds = max(1, min(int(data.get("rounds") or full), 50))
    except (TypeError, ValueError):
        return error("Nieprawidłowa liczba rund.")

    question_set = None
    slug = data.get("set") or ALL_SLUG
    if slug != ALL_SLUG:
        question_set = QuestionSet.query.filter_by(slug=slug, active=True).first()
        if not question_set:
            return error("Nie ma takiego zestawu.", 404)
    ids = _active_ids(question_set)
    if not ids:
        return error("Ten zestaw nie ma jeszcze pytań. Dodaj je w panelu /admin.", 404)

    picked = random.sample(ids, min(rounds, len(ids)))
    game = Game(
        question_ids=picked,
        user_id=g.user.id if g.user else None,
        set_id=question_set.id if question_set else None,
        ranked=g.user is not None and len(picked) == min(full, len(ids)),
    )
    db.session.add(game)
    db.session.commit()
    return jsonify(game_state(game)), 201


def _load_game(game_id, lock=False):
    query = db.session.query(Game).filter_by(id=game_id)
    game = (query.with_for_update() if lock else query).first()
    if game and game.user_id and (not g.user or g.user.id != game.user_id):
        return None
    return game


@bp.get("/games/<game_id>")
def get_game(game_id):
    game = _load_game(game_id)
    if not game:
        return error("Nie znaleziono gry.", 404)
    return jsonify(game_state(game))


# cebularz: with_for_update jest, bo Hubi klikał „Zgadnij” jak pojebany i robił dwie rundy naraz
# Hubi: to była mysz, nie ja
@bp.post("/games/<game_id>/guess")
def guess(game_id):
    game = _load_game(game_id, lock=True)
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
    dist, (closest_lat, closest_lng) = answer_distance(question, lat, lng)
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
    if game.finished:
        game.finished_at = datetime.now(timezone.utc)
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
            "answer": {**question.answer_dict(), "area": area_geojson([question.id]).get(question.id)},
            "closest": {"lat": closest_lat, "lng": closest_lng},
        }
    )
