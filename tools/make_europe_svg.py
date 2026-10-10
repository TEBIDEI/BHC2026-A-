"""Generuje app/templates/_europe_map.html — mapę Europy (SVG) do animacji logowania.

Kontury: world-atlas (Natural Earth, domena publiczna), rzut azymutalny równopolowy
Lamberta wyśrodkowany na Europie. Uruchom raz: python tools/make_europe_svg.py
"""
import json
import math
import urllib.request
from pathlib import Path

SOURCE = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json"
OUT = Path(__file__).resolve().parent.parent / "app" / "templates" / "_europe_map.html"

WIDTH, HEIGHT = 800, 640
LAT0, LON0 = math.radians(52), math.radians(14)
VIEW = (-24, 34, 44, 71)  # lon_min, lat_min, lon_max, lat_max — co ma się zmieścić w kadrze
KEEP = (-35, 25, 60, 80)  # państwa, które w ogóle rysujemy (bbox)

# Ikony (symbole w szablonie) na mapie, w kolejności trasy podróży.
LANDMARKS = [
    ("i-bigben", "Londyn", 51.50, -0.12),
    ("i-windmill", "Kinderdijk", 51.88, 4.64),
    ("i-stave", "Borgund", 61.05, 7.81),
    ("i-pierogi", "Kraków", 50.06, 19.94),
    ("i-coffee", "Wiedeń", 48.21, 16.37),
    ("i-pretzel", "Monachium", 48.14, 11.58),
    ("i-eiffel", "Paryż", 48.86, 2.29),
    ("i-paella", "Walencja", 39.47, -0.38),
    ("i-pizza", "Neapol", 40.85, 14.27),
    ("i-temple", "Ateny", 37.97, 23.73),
]


def project_raw(lon, lat):
    lam, phi = math.radians(lon) - LON0, math.radians(lat)
    denom = 1 + math.sin(LAT0) * math.sin(phi) + math.cos(LAT0) * math.cos(phi) * math.cos(lam)
    if denom <= 1e-9:
        return None
    k = math.sqrt(2 / denom)
    x = k * math.cos(phi) * math.sin(lam)
    y = k * (math.cos(LAT0) * math.sin(phi) - math.sin(LAT0) * math.cos(phi) * math.cos(lam))
    return x, -y


def make_projection():
    lon_min, lat_min, lon_max, lat_max = VIEW
    pts = [project_raw(lon, lat) for lon in range(lon_min, lon_max + 1, 2) for lat in (lat_min, lat_max)]
    pts += [project_raw(lon, lat) for lat in range(lat_min, lat_max + 1, 2) for lon in (lon_min, lon_max)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    scale = min(WIDTH / (max(xs) - min(xs)), HEIGHT / (max(ys) - min(ys)))
    ox = (WIDTH - (max(xs) - min(xs)) * scale) / 2 - min(xs) * scale
    oy = (HEIGHT - (max(ys) - min(ys)) * scale) / 2 - min(ys) * scale

    def project(lon, lat):
        p = project_raw(lon, lat)
        return None if p is None else (p[0] * scale + ox, p[1] * scale + oy)

    return project


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring_coords(ring, arcs):
    coords = []
    for idx in ring:
        arc = arcs[idx] if idx >= 0 else list(reversed(arcs[~idx]))
        coords.extend(arc[1:] if coords else arc)
    return coords


def polygons(geom):
    if geom["type"] == "Polygon":
        return [geom["arcs"]]
    if geom["type"] == "MultiPolygon":
        return geom["arcs"]
    return []


def ring_path(coords, project):
    out, last = [], None
    for lon, lat in coords:
        p = project(lon, lat)
        if p is None:
            continue
        if last and math.dist(p, last) < 2.2:  # upraszczanie: pomijamy punkty bliżej niż ~2 px
            continue
        out.append(p)
        last = p
    if len(out) < 3:
        return ""
    xs, ys = [p[0] for p in out], [p[1] for p in out]
    if max(xs) < -50 or min(xs) > WIDTH + 50 or max(ys) < -50 or min(ys) > HEIGHT + 50:
        return ""  # wyspa/ląd całkiem poza kadrem
    return "M" + "L".join(f"{x:.0f} {y:.0f}" for x, y in out) + "Z"


def main():
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "CultureGuessr-dev/0.1"})
    topo = json.load(urllib.request.urlopen(req, timeout=60))
    arcs = decode_arcs(topo)
    project = make_projection()

    paths = []
    for geom in topo["objects"]["countries"]["geometries"]:
        parts = []
        for poly in polygons(geom):
            outer = ring_coords(poly[0], arcs)
            lons, lats = [c[0] for c in outer], [c[1] for c in outer]
            if max(lons) < KEEP[0] or min(lons) > KEEP[2] or max(lats) < KEEP[1] or min(lats) > KEEP[3]:
                continue
            d = ring_path(outer, project)
            if d:
                parts.append(d)
        if parts:
            # Środek ciężkości (przybliżony) — do opóźnienia animacji od środka mapy na zewnątrz.
            nums = [float(v) for d in parts for v in d.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
            cx, cy = sum(nums[0::2]) / len(nums[0::2]), sum(nums[1::2]) / len(nums[1::2])
            dist = math.dist((cx, cy), (WIDTH / 2, HEIGHT / 2))
            paths.append((dist, "".join(parts)))

    paths.sort()
    max_dist = max(d for d, _ in paths) or 1
    country_svg = "\n".join(
        f'    <path class="land" pathLength="1" style="--d:{d / max_dist:.2f}" d="{p}"/>' for d, p in paths
    )

    spots = [(sym, name, *project(lon, lat)) for sym, name, lat, lon in LANDMARKS]
    route = "M" + " ".join(
        f"{x:.0f} {y:.0f}" if i == 0 else f"Q{(px + x) / 2 + (y - py) * 0.18:.0f} {(py + y) / 2 - (x - px) * 0.18:.0f} {x:.0f} {y:.0f}"
        for i, ((_, _, x, y), (_, _, px, py)) in enumerate(zip(spots, [spots[0]] + spots[:-1]))
    )
    spot_svg = "\n".join(
        f'    <g transform="translate({x:.0f} {y:.0f})"><g class="spot" style="--i:{i}">'
        f'<use href="#{sym}" x="-20" y="-20" width="40" height="40"/>'
        f'<text y="32" text-anchor="middle">{name}</text></g></g>'
        for i, (sym, name, x, y) in enumerate(spots)
    )

    OUT.write_text(
        "{# Wygenerowane przez tools/make_europe_svg.py — nie edytuj ręcznie. Kontury: Natural Earth. #}\n"
        f'<g class="countries">\n{country_svg}\n  </g>\n'
        f'  <mask id="route-mask"><path class="route-reveal" pathLength="1" d="{route}"/></mask>\n'
        f'  <path class="route" mask="url(#route-mask)" d="{route}"/>\n'
        f'  <g class="spots">\n{spot_svg}\n  </g>\n',
        encoding="utf-8",
    )
    print(f"Zapisano {OUT} ({OUT.stat().st_size // 1024} KB, {len(paths)} państw)")


if __name__ == "__main__":
    main()
