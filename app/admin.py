import hmac

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

from .models import CATEGORIES, Question, db
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
    search = request.args.get("q", "").strip()
    query = Question.query
    if category:
        query = query.filter(Question.category == category)
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
        search=search,
        total=Question.query.count(),
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    question = Question(category=request.args.get("category", "inne"), active=True)
    if request.method == "POST":
        if _fill_from_form(question):
            db.session.add(question)
            db.session.commit()
            flash(f"Dodano „{question.title}”.", "ok")
            if request.form.get("next") == "another":
                return redirect(url_for("admin.new", category=question.category))
            return redirect(url_for("admin.index"))
    return render_template("admin/form.html", question=question, categories=CATEGORIES)


@bp.route("/<int:question_id>/edit", methods=["GET", "POST"])
def edit(question_id):
    question = db.get_or_404(Question, question_id)
    if request.method == "POST":
        if _fill_from_form(question):
            db.session.commit()
            flash(f"Zapisano „{question.title}”.", "ok")
            if request.form.get("next") == "another":
                return redirect(url_for("admin.new", category=question.category))
            return redirect(url_for("admin.index"))
    return render_template("admin/form.html", question=question, categories=CATEGORIES)


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
    """Przepisuje dane z formularza do pytania. Zwraca False (i flashuje błędy), gdy są niepoprawne."""
    form = request.form
    errors = []

    question.title = form.get("title", "").strip()
    question.location_name = form.get("location_name", "").strip()
    question.description = form.get("description", "").strip() or None
    question.image_credit = form.get("image_credit", "").strip() or None
    question.active = form.get("active") == "on"
    category = form.get("category", "inne")
    question.category = category if category in CATEGORIES else "inne"

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
        # Formularz wraca z wpisanymi danymi; nowo zapisany plik nie jest potrzebny.
        if question.image_filename != old_filename:
            delete_image(question.image_filename)
            question.image_filename = old_filename
        for message in errors:
            flash(message, "error")
        return False
    if old_filename and question.image_filename != old_filename:
        delete_image(old_filename)
    return True
