import pytest

from app.scoring import haversine_km, score_from_distance


def test_haversine_warsaw_krakow():
    assert haversine_km(52.2297, 21.0122, 50.0647, 19.9450) == pytest.approx(252, abs=2)


def test_haversine_zero():
    assert haversine_km(50, 20, 50, 20) == 0


def test_perfect_radius_gives_max():
    assert score_from_distance(0) == 5000
    assert score_from_distance(15) == 5000


def test_score_decreases_and_stays_in_range():
    scores = [score_from_distance(d) for d in (16, 100, 500, 1000, 2000, 5000)]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 5000 for s in scores)
    assert score_from_distance(16) > 4990
