# CultureGuessr

Gra kulturowa w stylu GeoGuessr: widzisz zdjęcie (potrawa, strój, napis, zwyczaj), klikasz na mapie Europy, skąd pochodzi. Liczy się odległość w linii prostej, do 5000 pkt za rundę.

Flask + PostgreSQL/PostGIS + Leaflet, działa na telefonie i instaluje się jako PWA.

## Uruchomienie lokalne

Wymagania: Python 3.11+, Docker Desktop.

```bash
docker compose up -d
```

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -r requirements.txt
```

(na macOS/Linux: `.venv/bin/pip`, `.venv/bin/flask`)

```bash
cp .env.example .env
```

```bash
.venv/Scripts/flask --app app db upgrade
```

```bash
.venv/Scripts/flask --app app seed
```

```bash
.venv/Scripts/flask --app app run --debug --host 0.0.0.0 --port 5050
```

- Gra: http://localhost:5050
- Panel: http://localhost:5050/admin
- Telefon w tej samej sieci Wi-Fi: `http://<IP-komputera>:5050` (Windows może zapytać o zgodę zapory)

Postgres z PostGIS (`postgis/postgis:16-3.4-alpine`) działa na porcie **5433** (`geo` / `geo`, baza `cultureguessr`).

`flask seed` dodaje 4 zestawy (Stroje ludowe, Smaki Europy, Języki i pisma, Zabytki) i 42 pytania. Można go uruchamiać wielokrotnie, a istniejące pytania dostają tylko brakujące fakty i zestawy.

### Masz bazę sprzed migracji?

Jeśli baza powstała wcześniej przez `init-db` (bez tabeli `alembic_version`), oznacz ją raz jako wersję początkową, a potem zaktualizuj:

```bash
.venv/Scripts/flask --app app db stamp 0001_initial
```

```bash
.venv/Scripts/flask --app app db upgrade
```

Zmiana modeli → nowa migracja: `flask --app app db migrate -m "opis"`, przejrzyj plik w `migrations/versions/`, potem `db upgrade`.

## Konta i rankingi

- grać można bez konta; konto (nick + hasło) zapisuje wyniki: `/rejestracja`, `/logowanie`
- do rankingu trafiają tylko pełne gry zalogowanych graczy (`ROUNDS_PER_GAME` rund albo cały zestaw, jeśli jest krótszy)
- `/ranking/<zestaw>`: najlepsza gra każdego gracza, wszech czasów i w bieżącym tygodniu (od poniedziałku, czas polski)
- `/gracz/<nick>`: profil: historia gier, średnia na rundę, rekordy i miejsca w zestawach
- na serwerze ustaw własny `SECRET_KEY` w `.env` (podpisuje ciasteczko sesji)

## Dodawanie pytań (`/admin`)

- zdjęcie: przeciągnij plik, kliknij, **wklej Ctrl+V** albo podaj URL; pliki są zmniejszane do 1600 px i zapisywane jako WebP w `app/static/uploads/`
- lokalizacja: **kliknij na mapie** (pinezkę można przeciągać) albo wyszukaj miejsce
- „Zapisz i dodaj kolejne” zostawia wybraną kategorię; **Ctrl+Enter** zapisuje
- pytania można wyłączać bez usuwania
- **karta faktów**: pola pokazywane po zgadnięciu (np. dla stroju: nazwa, region, okazja, elementy, materiały); „Wstaw pola dla kategorii” podpowiada zestaw pól
- **zestawy** (`/admin/sets`): nazwa, opis, kolejność, widoczność i lista pytań z filtrem; pytanie może być w kilku zestawach

Ustaw `ADMIN_PASSWORD` w `.env`, żeby zabezpieczyć panel hasłem (Basic Auth, dowolny login).

## Obszary odpowiedzi (PostGIS)

Każde pytanie ma **poziom odpowiedzi**: miasto, powiat, region, państwo albo punkt (bez obszaru). Obszar to `geography(MultiPolygon, 4326)` w kolumnie `questions.area`:

- kliknięcie **wewnątrz** obszaru = 0 km = 5000 pkt, poza nim liczy się odległość do najbliższej granicy (`ST_Distance` na elipsoidzie), zob. `app/geo.py`
- po zgadnięciu gra rysuje obszar i linię do najbliższego punktu granicy (`ST_ClosestPoint`)
- granice przykładowych pytań: OpenStreetMap (© współtwórcy OSM, ODbL), pobrane przez `tools/fetch_areas.py` do `app/seed_areas.json`; `flask seed` uzupełnia obszary tylko tam, gdzie ich brak
- w panelu: wybierz poziom → „Znajdź granicę” (Nominatim) → wybierz wynik; „dołącz do obecnej” sumuje kilka granic (np. Sápmi = 4 regiony); można też wkleić własny GeoJSON
- przy zapisie granica jest naprawiana (`ST_MakeValid`), części scalane (`ST_UnaryUnion`) i upraszczane zależnie od poziomu

Przejście ze starego obrazu `postgres:16-alpine` na PostGIS zachowuje dane (ten sam wolumen i wersja Postgresa); potem `flask --app app db upgrade` i `flask --app app seed`.

## Punktacja

`app/scoring.py`:

- dystans = 0 wewnątrz obszaru, inaczej do granicy obszaru (PostGIS) albo, dla pytań bez obszaru, haversine do punktu
- ≤ `PERFECT_RADIUS_KM` (15 km) → 5000 pkt, dalej `5000 · e^(−(d−15)/SCORE_SCALE_KM)` (skala 750 km)
- przykładowo: 250 km ≈ 3660, 500 km ≈ 2620, 1000 km ≈ 1340, 2000 km ≈ 350 pkt


## Instalacja na telefonie (PWA)

Przeglądarki pozwalają zainstalować aplikację tylko przez HTTPS (lub na `localhost`). Do testów z telefonu najprościej wystawić lokalny serwer tunelem, np.:

```bash
cloudflared tunnel --url http://localhost:5050
```

Potem na telefonie: Chrome → menu → „Zainstaluj aplikację” / Safari → Udostępnij → „Do ekranu początkowego”.

## Struktura

```
app/
  __init__.py     create_app, filtry szablonów, komendy CLI (init-db, seed, reset-db)
  config.py       ustawienia (z .env)
  models.py       User, QuestionSet, Question, Game, Guess
  scoring.py      punkty (i haversine dla pytań bez obszaru)
  geo.py          obszary: GeoJSON → PostGIS, odległość do granicy
  api.py          /api: gra (stan gry trzymany na serwerze)
  auth.py         rejestracja, logowanie, wylogowanie
  ranking.py      rankingi i profil gracza
  admin.py        /admin: panel (pytania, zestawy)
  uploads.py      zapis zdjęć
  seed_data.py    przykładowe pytania (Wikimedia Commons)
  seed_areas.json granice obszarów przykładowych pytań (OpenStreetMap)
  templates/      HTML (Jinja)
  static/         css, js, ikony, manifest, service worker
migrations/       migracje bazy (Flask-Migrate / Alembic)
tests/            pytest (scoring, API, konta, rankingi, panel, obszary; Postgres + PostGIS)
tools/make_icons.py        ikony PWA
tools/make_europe_svg.py   mapa do animacji logowania (kontury: Natural Earth)
tools/fetch_areas.py       granice obszarów pytań z OpenStreetMap (Nominatim)
```

Styl „Notatnik podróżnika”, paleta Sepia. Tokeny są na górze `app/static/css/style.css`: `#F4ECD8` papier, `#3E2C1C` atrament, `#704214` główny, `#D08C60` akcent (taśma, margines), `#9A8467` linie, `#7A654C` drobny tekst, `#A3402E` pieczątka. Fonty: EB Garamond (tekst), Caveat (dopiski odręczne), Special Elite (pieczątka). Płasko: bez poświat, rozmytych cieni i gradientów kolorów.

## Testy

```bash
.venv/Scripts/python -m pytest
```

Testy potrzebują działającego kontenera (`docker compose up -d`) i same tworzą bazę `cultureguessr_test` z PostGIS. Inną bazę wskażesz zmienną `TEST_DATABASE_URL`.

Zdjęcia przykładowe pochodzą z Wikimedia Commons; autor i licencja są pokazywane po każdej rundzie.
