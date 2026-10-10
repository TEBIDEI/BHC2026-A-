"""Liczenie dystansu i punktów.

Na razie każde pytanie ma jeden punkt odpowiedzi. Gdy dojdą niestandardowe
obszary, wystarczy rozbudować `distance_km` (np. 0 km wewnątrz poligonu,
inaczej dystans do jego krawędzi) — reszta gry z niego korzysta.
"""
import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lng1, lat2, lng2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_km(question, lat, lng):
    return haversine_km(lat, lng, question.lat, question.lng)


def score_from_distance(distance, max_score=5000, scale_km=750, perfect_radius_km=15):
    if distance <= perfect_radius_km:
        return max_score
    return round(max_score * math.exp(-(distance - perfect_radius_km) / scale_km))
