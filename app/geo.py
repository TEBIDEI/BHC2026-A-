import json

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.dialects.postgresql import array

from .models import Question, db
from .scoring import haversine_km

SIMPLIFY = {"miasto": 0.0003, "powiat": 0.001, "region": 0.003, "panstwo": 0.006}
OUTPUT_DECIMALS = 3


class AreaError(ValueError):
    pass


def _point(lat, lng):
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)


def area_from_geojson(geojson, level):
    geometries = _extract_geometries(geojson)
    if not geometries:
        raise AreaError("GeoJSON nie zawiera wielokąta.")
    parts = [func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(g)), 4326) for g in geometries]
    collected = func.ST_UnaryUnion(func.ST_Collect(array(parts))) if len(parts) > 1 else parts[0]
    tolerance = SIMPLIFY.get(level, 0.001)
    cleaned = func.ST_Multi(
        func.ST_CollectionExtract(
            func.ST_MakeValid(func.ST_SimplifyPreserveTopology(func.ST_MakeValid(collected), tolerance)), 3
        )
    )
    try:
        with db.engine.connect() as conn:
            wkb, empty = conn.execute(select(func.ST_AsEWKB(cleaned), func.ST_IsEmpty(cleaned))).one()
    except DBAPIError as exc:
        raise AreaError(f"Niepoprawny GeoJSON: {str(exc.orig).splitlines()[0][:160]}") from exc
    if empty:
        raise AreaError("Obszar jest pusty po oczyszczeniu geometrii.")
    return func.ST_GeogFromWKB(wkb)


def _extract_geometries(data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise AreaError("To nie jest poprawny JSON.") from exc
    if not isinstance(data, dict):
        return []
    kind = data.get("type")
    if kind == "FeatureCollection":
        return [g for f in data.get("features", []) for g in _extract_geometries(f)]
    if kind == "Feature":
        return _extract_geometries(data.get("geometry") or {})
    if kind == "GeometryCollection":
        return [g for geom in data.get("geometries", []) for g in _extract_geometries(geom)]
    if kind in ("Polygon", "MultiPolygon"):
        return [data]
    return []


def answer_distance(question, lat, lng):
    if question.id is None or question.area is None:
        return haversine_km(lat, lng, question.lat, question.lng), (question.lat, question.lng)
    point = _point(lat, lng)
    area_geom = func.ST_GeomFromWKB(func.ST_AsBinary(Question.area), 4326)
    closest = func.ST_ClosestPoint(area_geom, point)
    row = db.session.execute(
        select(
            func.ST_Distance(Question.area, func.Geography(point)),
            func.ST_Y(closest),
            func.ST_X(closest),
        ).where(Question.id == question.id)
    ).one()
    return row[0] / 1000.0, (row[1], row[2])


def area_geojson(question_ids):
    ids = [i for i in question_ids if i]
    if not ids:
        return {}
    rows = db.session.execute(
        select(Question.id, func.ST_AsGeoJSON(Question.area, OUTPUT_DECIMALS))
        .where(Question.id.in_(ids), Question.area.isnot(None))
    ).all()
    return {qid: json.loads(geo) for qid, geo in rows}


def question_area_geojson(question, decimals=5):
    if question.id is None or question.area is None:
        return None
    with db.session.no_autoflush:
        geo = db.session.scalar(select(func.ST_AsGeoJSON(Question.area, decimals)).where(Question.id == question.id))
    return json.loads(geo) if geo else None
