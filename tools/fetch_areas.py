import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "seed_areas.json"
URL = "https://nominatim.openstreetmap.org/search?"
HEADERS = {"User-Agent": "CultureGuessr-dev/0.1 (seed areas; hackathon project)"}
THRESHOLD = {"miasto": 0.0005, "powiat": 0.002, "region": 0.005, "panstwo": 0.01}

AREAS = {
    "Pierogi": ("panstwo", "Polska", [("Polska", "pl")]),
    "Paella valenciana": ("region", "Wspólnota Walencka, Hiszpania", [("Comunitat Valenciana", "es")]),
    "Pastel de nata": ("miasto", "Lizbona, Portugalia", [("Lisboa", "pt")]),
    "Gulasz (gulyásleves)": ("panstwo", "Węgry", [("Magyarország", "hu")]),
    "Pizza Margherita": ("miasto", "Neapol, Włochy", [("Napoli", "it")]),
    "Fondue serowe": ("panstwo", "Szwajcaria", [("Schweiz", "ch")]),
    "Haggis, neeps and tatties": ("region", "Szkocja", [("Scotland", "gb")]),
    "Wiener Schnitzel": ("miasto", "Wiedeń, Austria", [("Wien", "at")]),
    "Musaka": ("panstwo", "Grecja", [("Ελλάδα", "gr")]),
    "Smørrebrød": ("panstwo", "Dania", [("Danmark", "dk")]),
    "Gofr z Liège": ("miasto", "Liège, Belgia", [("Liège", "be")]),
    "Bunad z Telemarku": ("region", "Telemark, Norwegia", [("Telemark", "no")]),
    "Strój z Miesbach (Tracht)": ("powiat", "Powiat Miesbach, Bawaria, Niemcy", [("Landkreis Miesbach", "de")]),
    "Traje de flamenca na Feria de Abril": ("region", "Andaluzja, Hiszpania", [("Andalucía", "es")]),
    "Gákti, strój Saamów": ("region", "Sápmi: północ Norwegii, Szwecji i Finlandii",
                             [("Finnmark", "no"), ("Troms", "no"), ("Norrbottens län", "se"), ("Lappi", "fi")]),
    "Strój łowicki": ("powiat", "Powiat łowicki, Polska", [("powiat łowicki", "pl")]),
    "Kilt": ("region", "Szkocja", [("Scotland", "gb")]),
    "Haft matyó": ("powiat", "Powiat Mezőkövesd, Węgry", [("Mezőkövesdi járás", "hu")]),
    "Strój z Volendam": ("miasto", "Edam-Volendam, Holandia", [("Edam-Volendam", "nl")]),
    "Czepek bigoudène": ("powiat", "Pays Bigouden, Bretania, Francja",
                         [("Communauté de communes du Pays Bigouden Sud", "fr"),
                          ("Communauté de communes du Haut Pays Bigouden", "fr")]),
    "Strój szaryski": ("region", "Kraj preszowski, Słowacja", [("Prešovský kraj", "sk")]),
    "Strój z Maramureszu": ("region", "Okręg Maramuresz, Rumunia", [("Maramureș", "ro")]),
    "Dwujęzyczny znak walijsko-angielski": ("region", "Walia, Wielka Brytania", [("Wales", "gb")]),
    "Znaki drogowe po baskijsku": ("region", "Kraj Basków i Nawarra, Hiszpania", [("Euskadi", "es"), ("Navarra", "es")]),
    "Tabliczka z nazwą ulicy po grecku": ("panstwo", "Grecja i Cypr", [("Ελλάδα", "gr"), ("Κύπρος", "cy")]),
    "Dwujęzyczna tabliczka irlandzko-angielska": ("panstwo", "Irlandia", [("Éire", "ie")]),
    "Znaki drogowe na Islandii": ("panstwo", "Islandia", [("Ísland", "is")]),
    "Tabliczka z nazwą ulicy po maltańsku": ("panstwo", "Malta", [("Malta", "mt")]),
    "Dwujęzyczne znaki francusko-bretońskie": ("region", "Bretania, Francja", [("Bretagne", "fr")]),
    "Tabliczka z nazwą ulicy po katalońsku": ("region", "Katalonia, Hiszpania", [("Catalunya", "es")]),
    "Fińsko-szwedzka tabliczka ulicy": ("panstwo", "Finlandia", [("Suomi", "fi")]),
    "Tabliczka ulicy w Belgradzie": ("panstwo", "Serbia", [("Србија", "rs")]),
    "Trulli": ("miasto", "Alberobello, Apulia, Włochy", [("Alberobello", "it")]),
    "Kościół klepkowy w Borgund": ("powiat", "Gmina Lærdal, Norwegia", [("Lærdal", "no")]),
    "Wiatraki w Kinderdijk": ("miasto", "Gmina Molenlanden (Kinderdijk), Holandia", [("Molenlanden", "nl")]),
    "Stari Most": ("miasto", "Mostar, Bośnia i Hercegowina", [("Grad Mostar", "ba")]),
    "Zamek Neuschwanstein": ("miasto", "Schwangau, Bawaria, Niemcy", [("Schwangau", "de")]),
    "Alhambra": ("miasto", "Grenada, Andaluzja, Hiszpania", [("Granada", "es")]),
    "Partenon": ("miasto", "Ateny, Grecja", [("Δήμος Αθηναίων", "gr")]),
    "Most Karola": ("miasto", "Praga, Czechy", [("Praha", "cz")]),
    "Oia na Santorini": ("miasto", "Santorini (gmina Thira), Grecja", [("Δήμος Θήρας", "gr")]),
    "Hallstatt": ("miasto", "Hallstatt, Austria", [("Hallstatt", "at")]),
}

GOOD_TYPES = {"administrative", "political", "territorial", "region", "country", "state", "city", "town",
              "village", "municipality", "county", "island"}


def search(query, country, level):
    params = {
        "q": query, "countrycodes": country, "format": "jsonv2", "limit": "5",
        "polygon_geojson": "1", "polygon_threshold": str(THRESHOLD[level]), "accept-language": "pl",
    }
    req = urllib.request.Request(URL + urllib.parse.urlencode(params), headers=HEADERS)
    results = json.load(urllib.request.urlopen(req, timeout=60))
    for r in results:
        geo = r.get("geojson", {})
        if geo.get("type") in ("Polygon", "MultiPolygon") and (r.get("type") in GOOD_TYPES or r.get("category") == "boundary"):
            return r
    return None


def main(only=None):
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    failed = []
    for title, (level, name, queries) in AREAS.items():
        if only and title not in only:
            continue
        parts = []
        for query, country in queries:
            time.sleep(1.2)
            r = search(query, country, level)
            if not r:
                print(f"  BRAK  {title!r}: {query} ({country})")
                failed.append(title)
                break
            print(f"  ok    {title!r}: {query} -> {r['display_name'][:70]} [{r['category']}/{r['type']}/{r.get('addresstype')}]")
            parts.append(r["geojson"])
        else:
            data[title] = {
                "level": level, "name": name,
                "geojson": {"type": "GeometryCollection", "geometries": parts} if len(parts) > 1 else parts[0],
            }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Zapisano {OUT} ({OUT.stat().st_size // 1024} KB, {len(data)} obszarów). Braki: {failed or 'brak'}")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
