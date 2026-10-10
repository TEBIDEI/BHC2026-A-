(() => {
  "use strict";

  const EUROPE = L.latLngBounds([33, -27], [72, 48]);
  const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  const STORAGE_KEY = "cg_game";
  const LINE_STYLE = { color: "#704214", weight: 2.5, dashArray: "1 7", lineCap: "round" };

  const AREA_STYLE = { color: "#704214", weight: 2, dashArray: "6 4", fillColor: "#D08C60", fillOpacity: 0.22, interactive: false };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Math.round(n).toLocaleString("pl-PL");
  const fmtKm = (km) => (km < 10 ? km.toFixed(1) : fmt(km)) + " km";

  const plural = (n, one, few, many) =>
    n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many;

  const thumb = (url) => (url || "").replace(/([?&]width=)\d+/, "$1240");

  const store = {
    get() { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } },
    set(v) { try { localStorage.setItem(STORAGE_KEY, v); } catch {  } },
    clear() { try { localStorage.removeItem(STORAGE_KEY); } catch {  } },
  };

  let game = null;
  let guessLatLng = null;
  let answered = false;
  let busy = false;
  let map, layer, summaryMap, summaryLayer;

  async function api(path, options = {}) {
    const res = await fetch("/api" + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(data.error || "Błąd serwera"), { status: res.status });
    return data;
  }

  function show(screen) {
    for (const id of ["screen-start", "screen-play", "screen-summary"]) $(id).hidden = id !== screen;

    $("stats").hidden = screen !== "screen-play";
    $("usernav").hidden = screen === "screen-play";
    if (screen === "screen-start") layoutRail();
  }

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

  const RAIL_SPEED = 22;
  const rail = { el: null, pos: 0, segment: 0, count: 0, hold: false, resumeAt: 0, selected: false, last: 0 };
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const EU_FLAG = (() => {
    const star = (cx, cy, r) => {
      const pts = [];
      for (let k = 0; k < 10; k++) {
        const a = -Math.PI / 2 + (k * Math.PI) / 5;
        const rad = k % 2 ? r * 0.382 : r;
        pts.push(`${(cx + rad * Math.cos(a)).toFixed(2)},${(cy + rad * Math.sin(a)).toFixed(2)}`);
      }
      return `<polygon points="${pts.join(" ")}"/>`;
    };
    const stars = Array.from({ length: 12 }, (_, i) => {
      const a = (i * Math.PI) / 6;
      return star(150 + 66.7 * Math.sin(a), 100 - 66.7 * Math.cos(a), 11.1);
    }).join("");
    return `<svg class="eu-flag" viewBox="0 0 300 200" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Flaga Europy"><rect width="300" height="200" fill="#003399"/><g fill="#FFCC00">${stars}</g></svg>`;
  })();

  function makeTile(s, clone) {
    const label = document.createElement("label");
    label.className = "set-tile";
    label.innerHTML = `
      <input type="radio" name="set">
      <span class="tile-photo">${s.cover ? '<img alt="" loading="lazy">' : EU_FLAG}</span>
      <span class="tile-body"><b></b><small></small><span class="count"></span></span>`;
    const input = label.querySelector("input");
    input.value = s.slug;
    if (clone) {
      label.setAttribute("aria-hidden", "true");
      input.tabIndex = -1;
    }
    if (s.cover) label.querySelector("img").src = thumb(s.cover);
    label.querySelector("b").textContent = s.name;
    label.querySelector("small").textContent = s.description || "";
    label.querySelector(".count").textContent = `${s.count} ${plural(s.count, "pytanie", "pytania", "pytań")}`;
    return label;
  }

  function centreTile(tile, smooth) {
    const el = rail.el;
    const target = tile.offsetLeft - (el.clientWidth - tile.offsetWidth) / 2;
    if (smooth) el.scrollTo({ left: target, behavior: "smooth" });
    else el.scrollLeft = target;
    rail.pos = target;
  }

  function wrapRail() {
    const el = rail.el;
    if (!rail.segment) return;
    if (rail.pos < rail.segment * 0.5) rail.pos += rail.segment;
    else if (rail.pos > rail.segment * 1.5) rail.pos -= rail.segment;
    el.scrollLeft = rail.pos;
  }

  function railLoop(t) {
    const dt = rail.last ? Math.min(0.05, (t - rail.last) / 1000) : 0;
    rail.last = t;
    const idle = !rail.hold && !rail.selected && performance.now() > rail.resumeAt;
    if (idle && !calm && !$("screen-start").hidden) {
      rail.pos += RAIL_SPEED * dt;
      wrapRail();
    }
    requestAnimationFrame(railLoop);
  }

  function pauseRail(ms) {
    rail.resumeAt = performance.now() + ms;
  }

  function chooseSet(input, smooth) {
    input.checked = true;
    rail.selected = true;
    centreTile(input.closest(".set-tile"), smooth);
    $("chosen-name").textContent = input.closest(".set-tile").querySelector("b").textContent;
    const options = $("start-options");
    const wasHidden = options.hidden;
    options.hidden = false;
    if (wasHidden && smooth) options.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function middleTiles() {
    return [...rail.el.children].slice(rail.count, rail.count * 2);
  }

  function layoutRail() {
    if (!rail.count || $("screen-start").hidden) return;
    const tiles = [...rail.el.children];
    rail.segment = tiles[rail.count].offsetLeft - tiles[0].offsetLeft;
    const checked = rail.el.querySelector("input:checked");
    const middle = middleTiles();
    const anchor = checked ? checked.closest(".set-tile")
      : middle.find((t) => t.querySelector("input").value === "wszystko") || middle[0];
    centreTile(anchor, false);
    wrapRail();
  }

  function setupRail(el) {
    rail.el = el;
    el.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") rail.hold = true; });
    el.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") rail.hold = false; });
    el.addEventListener("touchstart", () => pauseRail(4000), { passive: true });
    el.addEventListener("focusin", () => { rail.hold = true; });
    el.addEventListener("focusout", () => { rail.hold = false; });
    el.addEventListener("scroll", () => {
      if (Math.abs(el.scrollLeft - rail.pos) > 2) {
        rail.pos = el.scrollLeft;
        if (rail.segment && (rail.pos < rail.segment * 0.5 || rail.pos > rail.segment * 1.5)) wrapRail();
      }
    }, { passive: true });

    let drag = null;
    el.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      drag = { x: e.clientX, start: el.scrollLeft, moved: false };
    });
    window.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      if (Math.abs(dx) > 5) drag.moved = true;
      if (drag.moved) {
        rail.pos = drag.start - dx;
        el.scrollLeft = rail.pos;
      }
    });
    window.addEventListener("pointerup", () => {
      if (drag && drag.moved) {
        wrapRail();
        el.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); }, { capture: true, once: true });
      }
      drag = null;
    });
    el.addEventListener("change", (e) => {
      if (e.target.name === "set") chooseSet(e.target, true);
    });
    requestAnimationFrame(railLoop);
  }

  async function loadSets() {
    const list = $("set-list");
    try {
      const data = await api("/sets");
      const wanted = new URLSearchParams(location.search).get("zestaw");
      const sets = data.sets.filter((s) => s.count);
      list.innerHTML = "";
      if (!sets.length) {
        showStartError("Brak pytań w bazie. Dodaj je w panelu /admin albo uruchom „flask seed”.");
        return;
      }
      for (let copy = 0; copy < 3; copy++) {
        for (const s of sets) list.appendChild(makeTile(s, copy !== 1));
      }
      if (!rail.el) setupRail(list);
      rail.count = sets.length;
      const preset = wanted && middleTiles().find((t) => t.querySelector("input").value === wanted);
      if (preset) chooseSet(preset.querySelector("input"), false);
      layoutRail();
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

    const target = L.latLng(r.closest ? r.closest.lat : a.lat, r.closest ? r.closest.lng : a.lng);
    const bounds = L.latLngBounds([guessLatLng, target]);
    if (a.area) {
      const area = L.geoJSON(a.area, AREA_STYLE).addTo(layer);
      bounds.extend(area.getBounds());
    }
    if (r.distance_km > 0) {
      L.polyline([guessLatLng, target], LINE_STYLE).addTo(layer);
      L.marker(target, { icon: pin("answer"), keyboard: false }).addTo(layer);
    }

    $("guess-bar").hidden = true;
    $("result-points").textContent = fmt(r.score);
    $("result-distance").textContent = distanceNote(r.distance_km, r.score, r.max_round_score, Boolean(a.area));
    $("result-title").textContent = a.title;
    $("result-where").textContent = a.area ? `${a.location_name} · ${a.level_label.toLowerCase()}` : a.location_name;
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
    fitAroundResult(bounds);
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

  function distanceNote(km, score, max, isArea) {
    if (km === 0 && isArea) return "w granicach obszaru!";
    if (score >= max) return "w samo sedno!";
    return (km < 100 ? "blisko, " : "") + fmtKm(km) + " od celu";
  }

  function fitAroundResult(bounds) {
    const mapBox = $("map").getBoundingClientRect();
    const card = $("result").getBoundingClientRect();
    const overlaps = card.left < mapBox.right && card.right > mapBox.left;
    const extra = overlaps ? [40, card.height + 32] : [40, 40];

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
    const bounds = L.latLngBounds([]);
    for (const r of game.summary) {
      const g = L.latLng(r.guess.lat, r.guess.lng);
      L.marker(g, { icon: pin("guess"), keyboard: false }).addTo(summaryLayer);
      bounds.extend(g);
      if (r.answer) {
        const a = L.latLng(r.answer.lat, r.answer.lng);
        const target = r.closest ? L.latLng(r.closest.lat, r.closest.lng) : a;
        if (r.answer.area) bounds.extend(L.geoJSON(r.answer.area, AREA_STYLE).addTo(summaryLayer).getBounds());
        if (r.distance_km > 0) {
          L.polyline([g, target], LINE_STYLE).addTo(summaryLayer);
          if (r.answer.area) L.marker(target, { icon: pin("answer"), keyboard: false }).addTo(summaryLayer);
        }
        L.marker(a, { icon: pin("num", r.round), keyboard: false })
          .bindPopup(`<b>${escapeHtml(r.answer.title)}</b><br>${escapeHtml(r.answer.location_name)}`)
          .addTo(summaryLayer);
        bounds.extend(a);
      }

      const li = document.createElement("li");
      li.innerHTML = `
        <span class="n">${r.round}</span>
        <img alt="" loading="lazy">
        <span class="t"><b></b><span></span></span>
        <span class="s">${fmt(r.score)}<span>${fmtKm(r.distance_km)}</span></span>`;
      li.querySelector("img").src = r.answer ? thumb(r.answer.image) : "";
      if (r.answer) {
        li.querySelector("img").dataset.full = r.answer.image;
        li.querySelector("img").title = "Kliknij, aby powiększyć";
      }
      li.querySelector(".t b").textContent = r.answer ? r.answer.title : "(pytanie usunięte)";
      li.querySelector(".t span").textContent = r.answer ? r.answer.location_name : "";
      list.appendChild(li);
    }
    if (bounds.isValid()) summaryMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
    window.scrollTo(0, 0);
  }

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
      note.innerHTML = 'Grasz jako gość. <a href="/logowanie">Zaloguj się</a>, żeby wyniki trafiały do rankingu.';
    } else {
      note.textContent = "Ta gra nie liczy się do rankingu, bo liczą się tylko pełne gry.";
    }
    note.hidden = false;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

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

  $("start-form").addEventListener("submit", (e) => { e.preventDefault(); startGame(); });
  $("guess-btn").addEventListener("click", submitGuess);
  $("next-btn").addEventListener("click", nextRound);
  $("again-btn").addEventListener("click", startGame);
  $("menu-btn").addEventListener("click", () => show("screen-start"));

  $("photo").addEventListener("click", () => window.openZoom($("photo-img").src));
  $("summary-rounds").addEventListener("click", (e) => {
    const img = e.target.closest("img[data-full]");
    if (img) window.openZoom(img.dataset.full);
  });

  function exitGame() {
    if (!game || game.finished) return show("screen-start");
    if (!confirm("Przerwać grę? Ta gra nie trafi do rankingu.")) return;
    store.clear();
    game = null;
    show("screen-start");
  }
  $("exit-btn").addEventListener("click", exitGame);
  document.querySelector(".topbar .brand").addEventListener("click", (e) => {
    if ($("screen-start").hidden) {
      e.preventDefault();
      exitGame();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (!$("lightbox").hidden) return;
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
