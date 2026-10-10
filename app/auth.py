import re
from functools import wraps

from flask import Blueprint, g, redirect, render_template, request, session, url_for

from .models import User, db

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[\w.-]{3,20}$")
MIN_PASSWORD = 6


@bp.before_app_request
def load_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


@bp.app_context_processor
def inject_user():
    return {"current_user": g.get("user")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def _safe_next(default="/"):
    target = request.values.get("next", "")
    # Tylko ścieżki w obrębie aplikacji — bez otwartych przekierowań.
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target.rstrip("?") or default
    return default


def _log_in(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user.id


@bp.route("/logowanie", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(_safe_next())
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username_key=username.lower()).first()
        if user and user.check_password(password):
            _log_in(user)
            return redirect(_safe_next())
        error = "Nieprawidłowy nick albo hasło."
    return render_template("auth.html", mode="login", error=error, username=username, next=_safe_next(""))


@bp.route("/rejestracja", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(_safe_next())
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if not USERNAME_RE.match(username):
            error = "Nick: 3–20 znaków — litery, cyfry, kropka, myślnik lub podkreślnik."
        elif len(password) < MIN_PASSWORD:
            error = f"Hasło musi mieć co najmniej {MIN_PASSWORD} znaków."
        elif password != password2:
            error = "Hasła się różnią."
        elif User.query.filter_by(username_key=username.lower()).first():
            error = "Ten nick jest już zajęty."
        else:
            user = User(username=username, username_key=username.lower())
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            _log_in(user)
            return redirect(_safe_next())
    return render_template("auth.html", mode="register", error=error, username=username, next=_safe_next(""))


@bp.post("/wyloguj")
def logout():
    session.clear()
    return redirect(url_for("index"))
