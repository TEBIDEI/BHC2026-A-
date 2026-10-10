import json
from pathlib import Path

import pytest

from app.geo import AreaError, answer_distance, area_from_geojson
from app.models import Question, db
from app.seed_data import QUESTIONS

# Michał: testy na prawdziwym PostGIS, bo SQLite kłamał jak cebularz o swoim wyniku w rankingu
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[19.445, 49.5647], [20.445, 49.5647], [20.445, 50.5647], [19.445, 50.5647], [19.445, 49.5647]]],
}


def _seed():
    q = Question(
        title="Obszar", category="kuchnia", location_name="Okolice Krakowa", lat=50.0647, lng=19.945,
        image_url="https://example.com/x.jpg", area_level="powiat",
    )
    q.area = area_from_geojson(SQUARE, "powiat")
    db.session.add(q)


@pytest.fixture
def app(make_app):
    app = make_app(_seed)
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _question():
    return Question.query.filter_by(title="Obszar").one()


def test_click_inside_area_is_zero_km(app):
    km, closest = answer_distance(_question(), 50.3, 20.2)
    assert km == 0
    assert closest == pytest.approx((50.3, 20.2))


def test_click_outside_measures_to_border(app):
    km, (lat, lng) = answer_distance(_question(), 50.0647, 21.0)
    assert 38 < km < 41
    assert lng == pytest.approx(20.445, abs=1e-6) and lat == pytest.approx(50.0647, abs=0.01)


def test_guess_inside_area_gives_full_score(client):
    game = client.post("/api/games", json={"rounds": 1}).get_json()
    r = client.post(f"/api/games/{game['game_id']}/guess", json={"lat": 49.7, "lng": 19.6, "round": 1}).get_json()
    assert r["distance_km"] == 0 and r["score"] == 5000
    assert r["answer"]["level"] == "powiat"
    assert r["answer"]["area"]["type"] == "MultiPolygon"


def test_two_touching_parts_merge_into_valid_area(app):
    left = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    right = {"type": "Polygon", "coordinates": [[[0.9, 0], [2, 0], [2, 1], [0.9, 1], [0.9, 0]]]}
    value = area_from_geojson({"type": "GeometryCollection", "geometries": [left, right]}, "region")
    valid, parts = db.session.execute(
        db.select(db.func.ST_IsValid(db.func.geometry(value)), db.func.ST_NumGeometries(db.func.geometry(value)))
    ).one()
    assert valid and parts == 1


@pytest.mark.parametrize("bad", ['{"type": "Point", "coordinates": [1, 2]}', "nie json", '{"type": "Polygon", "coordinates": 5}'])
def test_rejects_bad_geojson(app, bad):
    with pytest.raises(AreaError):
        area_from_geojson(bad, "miasto")


def _form(**extra):
    data = {
        "title": "Obszar", "location_name": "Okolice Krakowa", "lat": "50.06", "lng": "19.94",
        "category": "kuchnia", "image_url": "https://example.com/x.jpg", "active": "on",
    }
    data.update(extra)
    return data


def test_admin_sets_and_clears_area(client, app):
    other = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    assert client.post("/admin/1/edit", data=_form(area_level="region", area_geojson=json.dumps(other))).status_code == 302
    db.session.expire_all()
    assert answer_distance(_question(), 0.5, 0.5)[0] == 0

    assert client.post("/admin/1/edit", data=_form(area_level="punkt")).status_code == 302
    db.session.expire_all()
    assert _question().area is None and _question().area_level == "punkt"


def test_admin_requires_area_for_non_point_level(client):
    res = client.post("/admin/1/edit", data=_form(area_level="miasto", area_clear="1"))
    assert "Wybierz granicę obszaru".encode() in res.data


def test_admin_rejects_invalid_area(client):
    res = client.post("/admin/1/edit", data=_form(area_level="miasto", area_geojson='{"type": "Point"}'))
    assert "Granica obszaru".encode() in res.data


def test_every_seed_question_has_an_area():
    areas = json.loads((Path(__file__).resolve().parent.parent / "app" / "seed_areas.json").read_text(encoding="utf-8"))
    missing = [q["title"] for q in QUESTIONS if q["title"] not in areas]
    assert not missing
    assert {a["level"] for a in areas.values()} <= {"miasto", "powiat", "region", "panstwo"}
