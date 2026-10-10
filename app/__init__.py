import click
from flask import Flask, render_template, send_from_directory

from .config import Config
from .models import CATEGORIES, Question, db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)

    from . import admin, api

    app.register_blueprint(api.bp)
    app.register_blueprint(admin.bp)

    @app.context_processor
    def inject_globals():
        return {"app_name": app.config["APP_NAME"]}

    @app.get("/")
    def index():
        return render_template("index.html", categories=CATEGORIES)

    # Service worker i manifest muszą być serwowane z katalogu głównego,
    # żeby obejmowały całą aplikację.
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
        """Tworzy tabele."""
        db.create_all()
        click.echo("Tabele utworzone.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Usunąć WSZYSTKIE dane?")
    def reset_db():
        """Usuwa i tworzy tabele od nowa."""
        db.drop_all()
        db.create_all()
        click.echo("Baza wyczyszczona.")

    @app.cli.command("seed")
    @click.option("--force", is_flag=True, help="Dodaj nawet jeśli baza ma już pytania.")
    def seed(force):
        """Dodaje przykładowe pytania."""
        from .seed_data import QUESTIONS

        db.create_all()
        if Question.query.count() and not force:
            click.echo("Baza ma już pytania — pomijam (użyj --force).")
            return
        for data in QUESTIONS:
            db.session.add(Question(**data))
        db.session.commit()
        click.echo(f"Dodano {len(QUESTIONS)} pytań.")
