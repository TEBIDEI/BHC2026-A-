import pytest

from app import create_app
from app.config import Config
from app.models import Question, QuestionSet, db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ADMIN_PASSWORD = ""
    ROUNDS_PER_GAME = 3


KRAKOW = {"lat": 50.0647, "lng": 19.945}


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        food = QuestionSet(slug="smaki", name="Smaki")
        db.session.add(food)
        for i in range(4):
            q = Question(
                title=f"Q{i}", category="kuchnia", location_name="Kraków", image_url="https://example.com/x.jpg",
                facts=[{"label": "Region", "value": "Małopolska"}], **KRAKOW,
            )
            if i < 3:
                q.sets.append(food)
            db.session.add(q)
        db.session.commit()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, name="ala", password="sekret1"):
    return client.post("/rejestracja", data={"username": name, "password": password, "password2": password})


def play(client, set_slug="smaki", rounds=None, point=KRAKOW):
    body = {"set": set_slug}
    if rounds:
        body["rounds"] = rounds
    game = client.post("/api/games", json=body).get_json()
    for rnd in range(1, game["rounds"] + 1):
        r = client.post(f"/api/games/{game['game_id']}/guess", json={**point, "round": rnd})
        assert r.status_code == 200
    return client.get(f"/api/games/{game['game_id']}").get_json()


def test_guest_game_is_not_ranked(client):
    res = client.post("/api/games", json={"set": "smaki"})
    assert res.status_code == 201
    game = res.get_json()
    assert "lat" not in game["question"]  # odpowiedź nie wycieka
    assert game["ranked"] is False

    state = play(client)
    assert state["finished"] and state["total_score"] == 15000
    assert state["summary"][0]["answer"]["facts"] == [{"label": "Region", "value": "Małopolska"}]
    assert "ranking" not in state


def test_sets_endpoint(client):
    sets = client.get("/api/sets").get_json()["sets"]
    assert [(s["slug"], s["count"]) for s in sets] == [("smaki", 3), ("wszystko", 4)]


def test_double_submit_rejected(client):
    game = client.post("/api/games", json={"rounds": 2}).get_json()
    url = f"/api/games/{game['game_id']}/guess"
    assert client.post(url, json={"lat": 50, "lng": 20, "round": 1}).status_code == 200
    assert client.post(url, json={"lat": 50, "lng": 20, "round": 1}).status_code == 409


def test_unknown_set(client):
    assert client.post("/api/games", json={"set": "nie-ma"}).status_code == 404


def test_register_login_logout(client):
    assert register(client).status_code == 302
    assert b"ala" in client.get("/").data
    client.post("/wyloguj")
    bad = client.post("/logowanie", data={"username": "ALA", "password": "zle-haslo"})
    assert "Nieprawidłowy".encode() in bad.data
    ok = client.post("/logowanie", data={"username": "ALA", "password": "sekret1"})
    assert ok.status_code == 302


def test_register_validation(client):
    assert "Hasła się różnią".encode() in client.post(
        "/rejestracja", data={"username": "ola", "password": "sekret1", "password2": "inne12"}).data
    register(client, "ola")
    client.post("/wyloguj")
    assert "zajęty".encode() in register(client, "OLA").data


def test_login_rejects_external_redirect(client):
    register(client)
    client.post("/wyloguj")
    res = client.post("/logowanie?next=//evil.example", data={"username": "ala", "password": "sekret1"})
    assert res.headers["Location"] == "/"


def test_ranked_game_and_leaderboard(client):
    register(client, "ala")
    state = play(client)
    assert state["ranked"] is True
    assert state["ranking"]["position"] == 1 and state["ranking"]["new_best"] is True

    client.post("/wyloguj")
    register(client, "bartek")
    worse = play(client, point={"lat": 52.23, "lng": 21.01})  # Warszawa, ~250 km od Krakowa
    assert worse["ranking"]["position"] == 2

    board = client.get("/ranking/smaki").get_data(as_text=True).split("leaderboard", 1)[1]
    assert board.index("ala") < board.index("bartek")
    assert "ala" in client.get("/ranking/smaki?okres=tydzien").get_data(as_text=True)
    assert client.get("/gracz/ala").status_code == 200


def test_short_game_not_ranked(client):
    register(client)
    state = play(client, rounds=2)
    assert state["ranked"] is False and "ranking" not in state


def test_other_player_cannot_touch_game(client, app):
    register(client, "ala")
    game = client.post("/api/games", json={"set": "smaki"}).get_json()
    other = app.test_client()
    assert other.get(f"/api/games/{game['game_id']}").status_code == 404
    assert other.post(f"/api/games/{game['game_id']}/guess", json=KRAKOW).status_code == 404


def test_admin_pages(client):
    for url in ["/admin/", "/admin/new", "/admin/sets", "/admin/sets/new", "/admin/sets/1/edit", "/admin/1/edit"]:
        assert client.get(url).status_code == 200, url


def test_admin_set_crud(client, app):
    res = client.post("/admin/sets/new", data={"name": "Łódzkie smaki", "questions": ["4"], "active": "on"})
    assert res.status_code == 302
    with app.app_context():
        qs = QuestionSet.query.filter_by(slug="lodzkie-smaki").one()
        assert [q.title for q in qs.questions] == ["Q3"]


def test_admin_question_facts_and_sets(client, app):
    data = {
        "title": "Q0", "location_name": "Kraków", "lat": "50", "lng": "20", "category": "kuchnia",
        "image_url": "https://example.com/x.jpg", "active": "on",
        "fact_label": ["Region", ""], "fact_value": ["Małopolska", "pominięte"], "sets": [],
    }
    assert client.post("/admin/1/edit", data=data).status_code == 302
    with app.app_context():
        q = db.session.get(Question, 1)
        assert q.facts == [{"label": "Region", "value": "Małopolska"}]
        assert q.sets == []
