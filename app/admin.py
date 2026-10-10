import hmac
import re
import unicodedata

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_

from .geo import AreaError, area_from_geojson, question_area_geojson
from .models import AREA_LEVELS, CATEGORIES, FACT_PRESETS, Question, QuestionSet, db
from .uploads import UploadError, delete_image, save_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def require_password():
    password = current_app.config["ADMIN_PASSWORD"]
    if not password:
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.password or "", password):
        return None
    return Response(
        "Wymagane hasło do panelu.", 401, {"WWW-Authenticate": 'Basic realm="CultureGuessr admin"'}
    )


@bp.get("/")
def index():
    category = request.args.get("category", "")
    set_slug = request.args.get("set", "")
    search = request.args.get("q", "").strip()
    query = Question.query
    if category:
        query = query.filter(Question.category == category)
    if set_slug:
        query = query.filter(Question.sets.any(QuestionSet.slug == set_slug))
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Question.title.ilike(like), Question.location_name.ilike(like)))
    questions = query.order_by(Question.created_at.desc()).all()
    return render_template(
        "admin/list.html",
        questions=questions,
        points=[
            {
                "id": q.id,
                "lat": q.lat,
                "lng": q.lng,
                "title": q.title,
                "active": q.active,
                "url": url_for("admin.edit", question_id=q.id),
            }
            for q in questions
        ],
        categories=CATEGORIES,
        category=category,
        sets=_all_sets(),
        set_slug=set_slug,
        search=search,
        total=Question.query.count(),
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    question = Question(category=request.args.get("category", "inne"), active=True, facts=[])
    preset_sets = [s.id for s in _all_sets() if s.slug in request.args.getlist("set")]
    return _question_form(question, preset_sets)


@bp.route("/<int:question_id>/edit", methods=["GET", "POST"])
def edit(question_id):
    question = db.get_or_404(Question, question_id)
    return _question_form(question, [s.id for s in question.sets])


def _question_form(question, selected_set_ids):
    all_sets = _all_sets()
    if request.method == "POST":
        selected_set_ids = [int(i) for i in request.form.getlist("sets") if i.isdigit()]
        if _fill_from_form(question):
            question.sets = [s for s in all_sets if s.id in selected_set_ids]
            if question.id is None:
                db.session.add(question)
            db.session.commit()
            flash(f"Zapisano „{question.title}”.", "ok")
            if request.form.get("next") == "another":
                chosen = [s.slug for s in question.sets]
                return redirect(url_for("admin.new", category=question.category, set=chosen))
            return redirect(url_for("admin.index"))
    with db.session.no_autoflush:
        return render_template(
            "admin/form.html",
            question=question,
            categories=CATEGORIES,
            sets=all_sets,
            selected_set_ids=selected_set_ids,
            fact_presets=FACT_PRESETS,
            levels=AREA_LEVELS,
            area_json=question_area_geojson(question),
        )


@bp.post("/<int:question_id>/toggle")
def toggle(question_id):
    question = db.get_or_404(Question, question_id)
    question.active = not question.active
    db.session.commit()
    return redirect(request.referrer or url_for("admin.index"))


@bp.post("/<int:question_id>/delete")
def delete(question_id):
    question = db.get_or_404(Question, question_id)
    delete_image(question.image_filename)
    db.session.delete(question)
    db.session.commit()
    flash(f"Usunięto „{question.title}”.", "ok")
    return redirect(url_for("admin.index"))


def _fill_from_form(question):
    form = request.form
    errors = []

    question.title = form.get("title", "").strip()
    question.location_name = form.get("location_name", "").strip()
    question.description = form.get("description", "").strip() or None
    question.image_credit = form.get("image_credit", "").strip() or None
    question.active = form.get("active") == "on"
    category = form.get("category", "inne")
    question.category = category if category in CATEGORIES else "inne"
    question.facts = [
        {"label": label.strip(), "value": value.strip()}
        for label, value in zip(form.getlist("fact_label"), form.getlist("fact_value"))
        if label.strip() and value.strip()
    ]

    if not question.title:
        errors.append("Podaj tytuł (co jest na zdjęciu).")
    if not question.location_name:
        errors.append("Podaj nazwę miejsca.")
    try:
        question.lat = float(form.get("lat", ""))
        question.lng = float(form.get("lng", ""))
        if not (-90 <= question.lat <= 90 and -180 <= question.lng <= 180):
            raise ValueError
    except ValueError:
        errors.append("Kliknij na mapie, żeby ustawić lokalizację.")

    level = form.get("area_level", "punkt")
    question.area_level = level if level in AREA_LEVELS else "punkt"
    new_area = form.get("area_geojson", "").strip()
    if question.area_level == "punkt" or form.get("area_clear") == "1":
        question.area = None
    if question.area_level != "punkt" and new_area:
        try:
            question.area = area_from_geojson(new_area, question.area_level)
        except AreaError as exc:
            errors.append(f"Granica obszaru: {exc}")
    if question.area_level != "punkt" and question.area is None and not errors:
        errors.append("Wybierz granicę obszaru („Znajdź granicę”) albo ustaw poziom „Punkt”.")

    old_filename = question.image_filename
    file = request.files.get("image_file")
    image_url = form.get("image_url", "").strip()
    if file and file.filename:
        try:
            question.image_filename = save_image(file)
            question.image_url = None
        except UploadError as exc:
            errors.append(str(exc))
    elif image_url and image_url != question.image_url:
        question.image_filename = None
        question.image_url = image_url
    if not question.image_filename and not question.image_url:
        errors.append("Dodaj zdjęcie (plik, wklejenie Ctrl+V albo URL).")

    if errors:
        if question.image_filename != old_filename:
            delete_image(question.image_filename)
            question.image_filename = old_filename
        for message in errors:
            flash(message, "error")
        return False
    if old_filename and question.image_filename != old_filename:
        delete_image(old_filename)
    return True


def _all_sets():
    return QuestionSet.query.order_by(QuestionSet.position, QuestionSet.name).all()


def slugify(text):
    text = text.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


@bp.get("/sets")
def sets_index():
    return render_template("admin/sets.html", sets=_all_sets())


@bp.route("/sets/new", methods=["GET", "POST"])
def set_new():
    return _set_form(QuestionSet(active=True, position=len(_all_sets())))


@bp.route("/sets/<int:set_id>/edit", methods=["GET", "POST"])
def set_edit(set_id):
    return _set_form(db.get_or_404(QuestionSet, set_id))


def _set_form(qs):
    questions = Question.query.order_by(Question.category, Question.title).all()
    selected = {q.id for q in qs.questions}
    if request.method == "POST":
        form = request.form
        selected = {int(i) for i in form.getlist("questions") if i.isdigit()}
        qs.name = form.get("name", "").strip()
        qs.slug = slugify(form.get("slug", "").strip() or qs.name)
        qs.description = form.get("description", "").strip() or None
        qs.active = form.get("active") == "on"
        try:
            qs.position = int(form.get("position", 0))
        except ValueError:
            qs.position = 0
        errors = []
        if not qs.name:
            errors.append("Podaj nazwę zestawu.")
        if not qs.slug:
            errors.append("Adres (slug) nie może być pusty.")
        with db.session.no_autoflush:
            taken = QuestionSet.query.filter(QuestionSet.slug == qs.slug, QuestionSet.id != qs.id).first()
        if qs.slug and taken:
            errors.append(f"Adres „{qs.slug}” zajmuje już zestaw „{taken.name}”.")
        if not errors:
            qs.questions = [q for q in questions if q.id in selected]
            if qs.id is None:
                db.session.add(qs)
            db.session.commit()
            flash(f"Zapisano zestaw „{qs.name}”.", "ok")
            return redirect(url_for("admin.sets_index"))
        for message in errors:
            flash(message, "error")
    with db.session.no_autoflush:
        return render_template(
            "admin/set_form.html", qs=qs, questions=questions, selected=selected, categories=CATEGORIES
        )


@bp.post("/sets/<int:set_id>/delete")
def set_delete(set_id):
    qs = db.get_or_404(QuestionSet, set_id)
    db.session.delete(qs)
    db.session.commit()
    flash(f"Usunięto zestaw „{qs.name}” (pytania zostały).", "ok")
    return redirect(url_for("admin.sets_index"))
