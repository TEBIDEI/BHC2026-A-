import pytest

from app import create_app
from app.config import Config
from app.models import Question, db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ADMIN_PASSWORD = ""


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        for i in range(3):
            db.session.add(Question(
                title=f"Q{i}", category="kuchnia", location_name="Kraków",
                lat=50.0647, lng=19.945, image_url="https://example.com/x.jpg",
            ))
        db.session.commit()
        yield app.test_client()


def test_full_game(client):
    res = client.post("/api/games", json={"rounds": 3})
    assert res.status_code == 201
    game = res.get_json()
    assert "lat" not in game["question"]  # odpowiedź nie wycieka

    for rnd in range(1, 4):
        r = client.post(f"/api/games/{game['game_id']}/guess", json={"lat": 50.0647, "lng": 19.945, "round": rnd})
        assert r.status_code == 200
        assert r.get_json()["score"] == 5000

    state = client.get(f"/api/games/{game['game_id']}").get_json()
    assert state["finished"] and state["total_score"] == 15000
    assert len(state["summary"]) == 3


def test_double_submit_rejected(client):
    game = client.post("/api/games", json={"rounds": 2}).get_json()
    url = f"/api/games/{game['game_id']}/guess"
    assert client.post(url, json={"lat": 50, "lng": 20, "round": 1}).status_code == 200
    assert client.post(url, json={"lat": 50, "lng": 20, "round": 1}).status_code == 409


def test_empty_category(client):
    assert client.post("/api/games", json={"category": "jezyk"}).status_code == 404


def test_admin_list(client):
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/new").status_code == 200
