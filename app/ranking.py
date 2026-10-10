"""Rankingi (najlepsza gra w zestawie, wszech czasów i tygodniowy) oraz profil gracza."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, render_template, request
from sqlalchemy import func

from .models import Game, QuestionSet, User, db

bp = Blueprint("ranking", __name__)

TZ = ZoneInfo("Europe/Warsaw")
ALL_SLUG = "wszystko"  # gry „wszystkie pytania” (bez zestawu)
PERIODS = {"zawsze": "Wszech czasów", "tydzien": "Ten tydzień"}


def week_start(now=None):
    """Poniedziałek 00:00 czasu polskiego, w UTC."""
    local = (now or datetime.now(timezone.utc)).astimezone(TZ)
    monday = datetime.combine(local.date() - timedelta(days=local.weekday()), time(), TZ)
    return monday.astimezone(timezone.utc)


def _ranked_games(set_id, since=None):
    query = db.session.query(Game).filter(Game.ranked.is_(True), Game.finished_at.isnot(None))
    query = query.filter(Game.set_id == set_id) if set_id else query.filter(Game.set_id.is_(None))
    if since:
        query = query.filter(Game.finished_at >= since)
    return query


def leaderboard(set_id, since=None, limit=50):
    """Najlepszy wynik jednej gry każdego gracza, malejąco."""
    best = func.max(Game.total_score).label("best")
    rows = (
        _ranked_games(set_id, since)
        .with_entities(Game.user_id, best, func.count(Game.id).label("games"))
        .group_by(Game.user_id)
        .subquery()
    )
    return (
        db.session.query(User.username, rows.c.best, rows.c.games)
        .join(rows, rows.c.user_id == User.id)
        .order_by(rows.c.best.desc(), User.username_key)
        .limit(limit)
        .all()
    )


def position(user_id, set_id, since=None):
    """Miejsce gracza w rankingu (1 = najlepszy) i jego najlepszy wynik, albo (None, None)."""
    games = _ranked_games(set_id, since)
    mine = games.filter(Game.user_id == user_id).with_entities(func.max(Game.total_score)).scalar()
    if mine is None:
        return None, None
    per_user = games.with_entities(func.max(Game.total_score).label("best")).group_by(Game.user_id).subquery()
    better = db.session.query(func.count()).select_from(per_user).filter(per_user.c.best > mine).scalar()
    return better + 1, mine


def set_choices():
    sets = QuestionSet.query.filter_by(active=True).order_by(QuestionSet.position, QuestionSet.name).all()
    return [(s.slug, s.name) for s in sets] + [(ALL_SLUG, "Wszystkie pytania")]


@bp.get("/ranking")
@bp.get("/ranking/<slug>")
def board(slug=None):
    choices = set_choices()
    slug = slug or choices[0][0]
    if slug == ALL_SLUG:
        set_id, title = None, "Wszystkie pytania"
    else:
        qs = QuestionSet.query.filter_by(slug=slug).first_or_404()
        set_id, title = qs.id, qs.name
    period = request.args.get("okres", "zawsze")
    if period not in PERIODS:
        period = "zawsze"
    since = week_start() if period == "tydzien" else None
    return render_template(
        "ranking.html",
        rows=leaderboard(set_id, since),
        choices=choices,
        slug=slug,
        title=title,
        period=period,
        periods=PERIODS,
        week_from=week_start().astimezone(TZ) if period == "tydzien" else None,
    )


@bp.get("/gracz/<username>")
def profile(username):
    user = User.query.filter_by(username_key=username.lower()).first()
    if not user:
        abort(404)
    games = (
        Game.query.filter(Game.user_id == user.id, Game.finished_at.isnot(None))
        .order_by(Game.finished_at.desc())
        .all()
    )
    rounds = sum(g.rounds for g in games)
    stats = {
        "games": len(games),
        "avg_round": round(sum(g.total_score for g in games) / rounds) if rounds else 0,
        "best": max((g.total_score for g in games), default=0),
    }
    bests = []
    for slug, name in set_choices():
        set_id = None
        if slug != ALL_SLUG:
            set_id = QuestionSet.query.filter_by(slug=slug).with_entities(QuestionSet.id).scalar()
        pos, best = position(user.id, set_id)
        if best is not None:
            bests.append({"slug": slug, "name": name, "best": best, "position": pos})
    return render_template("profile.html", player=user, games=games[:30], stats=stats, bests=bests)
