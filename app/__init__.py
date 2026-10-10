from pathlib import Path
from zoneinfo import ZoneInfo

import click
from flask import Flask, render_template, send_from_directory
from flask_migrate import Migrate, upgrade

from .config import Config
from .models import Question, QuestionSet, db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    Migrate(app, db, directory=str(Path(__file__).resolve().parent.parent / "migrations"))

    from . import admin, api, auth, ranking

    app.register_blueprint(auth.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(ranking.bp)
    app.register_blueprint(admin.bp)

    @app.context_processor
    def inject_globals():
        return {"app_name": app.config["APP_NAME"]}

    @app.template_filter("pkt")
    def format_points(value):
        return f"{int(value or 0):,}".replace(",", " ")

    @app.template_filter("gier")
    def games_count(n):
        if n == 1:
            return f"{n} gra"
        if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return f"{n} gry"
        return f"{n} gier"

    @app.template_filter("data")
    def format_date(value, godzina=True):
        if not value:
            return ""
        local = value.astimezone(ZoneInfo("Europe/Warsaw"))
        return local.strftime("%d.%m.%Y, %H:%M" if godzina else "%d.%m.%Y")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/sw.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(
            app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json"
        )

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        upgrade()
        click.echo("Baza aktualna.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Usunąć WSZYSTKIE dane?")
    def reset_db():
        db.drop_all()
        db.session.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
        db.session.commit()
        upgrade()
        click.echo("Baza wyczyszczona.")

    @app.cli.command("seed")
    def seed():
        import json

        from .geo import area_from_geojson
        from .seed_data import QUESTIONS, SETS

        areas_file = Path(__file__).resolve().parent / "seed_areas.json"
        seed_areas = json.loads(areas_file.read_text(encoding="utf-8")) if areas_file.exists() else {}

        sets = {}
        for position, data in enumerate(SETS):
            qs = QuestionSet.query.filter_by(slug=data["slug"]).first()
            if not qs:
                qs = QuestionSet(position=position, **data)
                db.session.add(qs)
            sets[data["slug"]] = qs

        added = updated = with_area = 0
        for data in QUESTIONS:
            data = dict(data)
            set_slugs = data.pop("sets", [])
            question = Question.query.filter_by(title=data["title"]).first()
            if question:
                if not question.facts and data.get("facts"):
                    question.facts = data["facts"]
                    updated += 1
            else:
                question = Question(**data)
                db.session.add(question)
                added += 1
            for slug in set_slugs:
                if sets[slug] not in question.sets:
                    question.sets.append(sets[slug])
            area = seed_areas.get(question.title)
            if area and question.area is None:
                question.area = area_from_geojson(area["geojson"], area["level"])
                question.area_level = area["level"]
                question.location_name = area["name"]
                with_area += 1
        db.session.commit()
        click.echo(
            f"Zestawy: {len(sets)}. Nowe pytania: {added}, uzupełnione fakty: {updated}, nowe obszary: {with_area}."
        )
