(() => {
  "use strict";

  const EUROPE = L.latLngBounds([33, -27], [72, 48]);
  const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  const STORAGE_KEY = "cg_game";
  const LINE_STYLE = { color: "#704214", weight: 2.5, dashArray: "1 7", lineCap: "round" };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Math.round(n).toLocaleString("pl-PL");
  const fmtKm = (km) => (km < 10 ? km.toFixed(1) : fmt(km)) + " km";
  // Polska odmiana: 1 pytanie, 2 pytania, 5 pytań, 22 pytania.
  const plural = (n, one, few, many) =>
    n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many;
  // Miniatury z Wikimedia Commons w mniejszej rozdzielczości.
  const thumb = (url) => (url || "").replace(/([?&]width=)\d+/, "$1240");

  const store = {
    get() { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } },
    set(v) { try { localStorage.setItem(STORAGE_KEY, v); } catch { /* prywatne okno */ } },
    clear() { try { localStorage.removeItem(STORAGE_KEY); } catch { /* j.w. */ } },
  };

  let game = null;        // stan z /api/games/<id>
  let guessLatLng = null;
  let answered = false;
  let busy = false;
  let map, layer, summaryMap, summaryLayer;

  // ---------- API ----------
  async function api(path, options = {}) {
    const res = await fetch("/api" + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(data.error || "Błąd serwera"), { status: res.status });
    return data;
  }

  // ---------- Ekrany ----------
  function show(screen) {
    for (const id of ["screen-start", "screen-play", "screen-summary"]) $(id).hidden = id !== screen;
    // W trakcie gry pasek pokazuje rundę i punkty, poza nią — nawigację gracza.
    $("stats").hidden = screen !== "screen-play";
    $("usernav").hidden = screen === "screen-play";
  }

  // Znaczniki: krzyżyk gracza, kółko z kropką dla odpowiedzi, numer rundy w podsumowaniu.
  const X_SVG = '<svg class="pin-x" viewBox="0 0 26 26"><path class="halo" d="M6 6L20 20M20 6L6 20"/><path class="ink" d="M6 6L20 20M20 6L6 20"/></svg>';
  const PINS = {
    guess: () => ({ html: X_SVG, size: 26 }),
    answer: () => ({ html: '<div class="pin-answer"></div>', size: 24 }),
    num: (n) => ({ html: `<div class="pin-num">${n}</div>`, size: 26 }),
  };
  function pin(type, arg) {
    const { html, size } = PINS[type](arg);
    return L.divIcon({ className: "", html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
  }

  // Restartuje animację CSS (np. pieczątki) przez zdjęcie i ponowne dodanie klasy.
  function replay(el, cls) {
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
  }

  function baseMap(el) {
    const m = L.map(el, {
      minZoom: 2, maxZoom: 12, worldCopyJump: false,
      maxBounds: EUROPE.pad(0.15), maxBoundsViscosity: 0.8,
      zoomSnap: 0.25,
    });
    L.tileLayer(TILES, { attribution: TILE_ATTR, maxZoom: 19 }).addTo(m);
    m.fitBounds(EUROPE);
    return m;
  }

  // ---------- Start ----------
  async function loadSets() {
    const list = $("set-list");
    try {
      const data = await api("/sets");
      const wanted = new URLSearchParams(location.search).get("zestaw");
      const sets = data.sets.filter((s) => s.count);
      list.innerHTML = "";
      sets.forEach((s, i) => {
        const label = document.createElement("label");
        label.className = "toc-item";
        label.innerHTML = `
          <input type="radio" name="set">
          ${s.cover ? '<img alt="" loading="lazy">' : '<span class="blank"></span>'}
          <span><b></b><small></small></span>
          <span class="count"></span>`;
        const input = label.querySelector("input");
        input.value = s.slug;
        input.checked = wanted ? s.slug === wanted : i === 0;
        if (s.cover) label.querySelector("img").src = thumb(s.cover);
        label.querySelector("b").textContent = s.name;
        label.querySelector("small").textContent = s.description || "";
        label.querySelector(".count").textContent = `${s.count} ${plural(s.count, "pytanie", "pytania", "pytań")}`;
        list.appendChild(label);
      });
      if (!list.querySelector("input:checked") && sets.length) list.querySelector("input").checked = true;
      if (!sets.length) showStartError("Brak pytań w bazie — dodaj je w panelu /admin albo uruchom „flask seed”.");
    } catch (e) {
      list.innerHTML = "";
      showStartError("Nie udało się połączyć z serwerem.");
    }
  }

  function showStartError(msg) {
    $("start-error").textContent = msg;
    $("start-error").hidden = !msg;
  }

  async function startGame() {
    const form = new FormData($("start-form"));
    showStartError("");
    $("start-btn").disabled = true;
    try {
      game = await api("/games", {
        method: "POST",
        body: JSON.stringify({ set: form.get("set"), rounds: Number(form.get("rounds")) }),
      });
      store.set(game.game_id);
      showRound();
    } catch (e) {
      showStartError(e.message);
    } finally {
      $("start-btn").disabled = false;
    }
  }

  // ---------- Runda ----------
  function showRound() {
    show("screen-play");
    $("screen-play").classList.remove("answered");
    if (!map) {
      map = baseMap("map");
      layer = L.layerGroup().addTo(map);
      map.on("click", onMapClick);
    }
    map.setMaxBounds(EUROPE.pad(0.15));
    map.invalidateSize();
    layer.clearLayers();
    map.fitBounds(EUROPE);

    guessLatLng = null;
    answered = false;
    $("result").hidden = true;
    $("guess-bar").hidden = false;
    setGuessButton();

    const q = game.question;
    const img = $("photo-img");
    img.classList.add("loading");
    img.onload = () => img.classList.remove("loading");
    img.src = q ? q.image : "";
    replay($("print"), "drop");
    $("photo-tag").textContent = q ? q.category_label.toLowerCase() : "";
    $("photo-credit").hidden = true;
    updateStats(game.round, game.rounds, game.total_score);
  }

  function updateStats(round, rounds, total) {
    $("stat-round").textContent = `${round} z ${rounds}`;
    $("stat-score").textContent = fmt(total);
  }

  function setGuessButton() {
    const btn = $("guess-btn");
    btn.disabled = !guessLatLng || busy;
    btn.textContent = guessLatLng ? "Tu! Sprawdź" : "Postaw krzyżyk na mapie";
  }

  function onMapClick(e) {
    if (answered) return;
    guessLatLng = e.latlng;
    layer.clearLayers();
    L.marker(guessLatLng, { icon: pin("guess"), keyboard: false }).addTo(layer);
    setGuessButton();
  }

  async function submitGuess() {
    if (!guessLatLng || answered || busy) return;
    busy = true;
    setGuessButton();
    try {
      const r = await api(`/games/${game.game_id}/guess`, {
        method: "POST",
        body: JSON.stringify({ lat: guessLatLng.lat, lng: guessLatLng.lng, round: game.round }),
      });
      answered = true;
      showResult(r);
    } catch (e) {
      if (e.status === 409 || e.status === 410) return resume(game.game_id);
      alert(e.message);
    } finally {
      busy = false;
      setGuessButton();
    }
  }

  function showResult(r) {
    const a = r.answer;
    const answerLatLng = L.latLng(a.lat, a.lng);
    L.polyline([guessLatLng, answerLatLng], LINE_STYLE).addTo(layer);
    L.marker(answerLatLng, { icon: pin("answer"), keyboard: false }).addTo(layer);

    $("guess-bar").hidden = true;
    $("result-points").textContent = fmt(r.score);
    $("result-distance").textContent = distanceNote(r.distance_km, r.score, r.max_round_score);
    $("result-title").textContent = a.title;
    $("result-where").textContent = a.location_name;
    $("result-desc").textContent = a.description || "";
    $("result-desc").hidden = !a.description;
    renderFacts(a.facts || []);
    if (a.image_credit) {
      $("photo-credit").textContent = "fot. " + a.image_credit;
      $("photo-credit").hidden = false;
    }
    $("next-btn").textContent = r.finished ? "Zobacz podsumowanie" : "Przewróć stronę →";
    $("result").hidden = false;
    replay($("result-stamp"), "pressed");
    $("screen-play").classList.add("answered");
    map.invalidateSize();
    updateStats(r.round, r.rounds, r.total_score);
    game.finished = r.finished;
    fitAroundResult(L.latLngBounds([guessLatLng, answerLatLng]));
    $("next-btn").focus({ preventScroll: true });
  }

  function renderFacts(facts) {
    const dl = $("result-facts");
    dl.innerHTML = "";
    for (const f of facts) {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = f.label;
      dd.textContent = f.value;
      dl.append(dt, dd);
    }
    dl.hidden = !facts.length;
  }

  // Odręczny dopisek pod pieczątką.
  function distanceNote(km, score, max) {
    if (score >= max) return "w samo sedno!";
    return (km < 100 ? "blisko — " : "") + fmtKm(km) + " od celu";
  }

  // Dopasowuje mapę tak, żeby karta wyniku nie zasłaniała pinezek.
  function fitAroundResult(bounds) {
    const mapBox = $("map").getBoundingClientRect();
    const card = $("result").getBoundingClientRect();
    const sideBySide = mapBox.width - card.width > 320;
    const extra = sideBySide ? [card.width + 32, 40] : [40, card.height + 32];
    // Ograniczenie do Europy cofałoby widok pod kartkę — na czas wyniku je zdejmujemy.
    map.setMaxBounds(null);
    map.fitBounds(bounds, { paddingTopLeft: [40, 40], paddingBottomRight: extra, maxZoom: 7 });
  }

  async function nextRound() {
    if (busy) return;
    busy = true;
    try {
      game = await api(`/games/${game.game_id}`);
      game.finished ? showSummary() : showRound();
    } catch (e) {
      alert(e.message);
    } finally {
      busy = false;
    }
  }

  // ---------- Podsumowanie ----------
  function showSummary() {
    store.clear();
    show("screen-summary");
    updateStats(game.rounds, game.rounds, game.total_score);
    $("summary-total").textContent = fmt(game.total_score);
    replay($("summary-stamp"), "pressed");
    renderRankNote();
    $("summary-max").textContent = fmt(game.max_score);

    if (!summaryMap) {
      summaryMap = baseMap("summary-map");
      summaryLayer = L.layerGroup().addTo(summaryMap);
    }
    summaryMap.invalidateSize();
    summaryLayer.clearLayers();

    const list = $("summary-rounds");
    list.innerHTML = "";
    const points = [];
    for (const r of game.summary) {
      const g = L.latLng(r.guess.lat, r.guess.lng);
      L.marker(g, { icon: pin("guess"), keyboard: false }).addTo(summaryLayer);
      points.push(g);
      if (r.answer) {
        const a = L.latLng(r.answer.lat, r.answer.lng);
        L.polyline([g, a], LINE_STYLE).addTo(summaryLayer);
        L.marker(a, { icon: pin("num", r.round), keyboard: false })
          .bindPopup(`<b>${escapeHtml(r.answer.title)}</b><br>${escapeHtml(r.answer.location_name)}`)
          .addTo(summaryLayer);
        points.push(a);
      }

      const li = document.createElement("li");
      li.innerHTML = `
        <span class="n">${r.round}</span>
        <img alt="" loading="lazy">
        <span class="t"><b></b><span></span></span>
        <span class="s">${fmt(r.score)}<span>${fmtKm(r.distance_km)}</span></span>`;
      li.querySelector("img").src = r.answer ? thumb(r.answer.image) : "";
      li.querySelector(".t b").textContent = r.answer ? r.answer.title : "(pytanie usunięte)";
      li.querySelector(".t span").textContent = r.answer ? r.answer.location_name : "";
      list.appendChild(li);
    }
    if (points.length) summaryMap.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 6 });
    window.scrollTo(0, 0);
  }

  // Informacja pod wynikiem: miejsce w rankingu albo zachęta do zalogowania.
  function renderRankNote() {
    const note = $("rank-note");
    const r = game.ranking;
    if (r) {
      note.innerHTML = `<span class="hand"></span> <span class="txt"></span> <a></a>`;
      note.querySelector(".hand").textContent = r.new_best ? "Nowy rekord!" : "Zapisane.";
      note.querySelector(".txt").textContent =
        `Miejsce #${r.position} w rankingu „${game.set.name}”` +
        (r.week_position ? `, w tym tygodniu #${r.week_position}.` : ".");
      note.querySelector("a").textContent = "Zobacz ranking";
      note.querySelector("a").href = r.url;
    } else if (!document.body.dataset.user) {
      note.innerHTML = 'Grasz jako gość — <a href="/logowanie">zaloguj się</a>, żeby wyniki trafiały do rankingu.';
    } else {
      note.textContent = "Ta gra nie liczy się do rankingu — liczą się tylko pełne gry.";
    }
    note.hidden = false;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------- Wznawianie po odświeżeniu ----------
  async function resume(id) {
    try {
      game = await api(`/games/${id}`);
      if (game.finished) { store.clear(); show("screen-start"); return; }
      showRound();
    } catch {
      store.clear();
      show("screen-start");
    }
  }

  // ---------- Zdarzenia ----------
  $("start-form").addEventListener("submit", (e) => { e.preventDefault(); startGame(); });
  $("guess-btn").addEventListener("click", submitGuess);
  $("next-btn").addEventListener("click", nextRound);
  $("again-btn").addEventListener("click", startGame);
  $("menu-btn").addEventListener("click", () => show("screen-start"));

  $("photo").addEventListener("click", () => {
    const img = $("photo-img");
    if (!img.src) return;
    $("lightbox").querySelector("img").src = img.src;
    $("lightbox").hidden = false;
  });
  $("lightbox").addEventListener("click", () => { $("lightbox").hidden = true; });

  document.addEventListener("keydown", (e) => {
    if (!$("lightbox").hidden && e.key === "Escape") { $("lightbox").hidden = true; return; }
    if ($("screen-play").hidden || (e.key !== "Enter" && e.key !== " ")) return;
    if (e.target.closest("button, input, a")) return;
    e.preventDefault();
    answered ? nextRound() : submitGuess();
  });

  loadSets();
  const saved = store.get();
  if (saved) resume(saved);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
})();
