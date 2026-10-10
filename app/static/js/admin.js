(() => {
  "use strict";

  const EUROPE = L.latLngBounds([33, -27], [72, 48]);
  const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  const $ = (id) => document.getElementById(id);

  function baseMap(el) {
    const m = L.map(el, { zoomSnap: 0.25, minZoom: 2 });
    L.tileLayer(TILES, { attribution: TILE_ATTR, maxZoom: 19 }).addTo(m);
    m.fitBounds(EUROPE);
    return m;
  }

  function keepFitted(m, fit) {
    let userMoved = false;
    const el = m.getContainer();
    for (const ev of ["mousedown", "touchstart", "wheel", "keydown"]) {
      el.addEventListener(ev, () => (userMoved = true), { passive: true });
    }
    fit();
    new ResizeObserver(() => {
      m.invalidateSize();
      if (!userMoved) fit();
    }).observe(el);
  }

  function pin(cls) {
    return L.divIcon({ className: "", html: `<div class="${cls}"></div>`, iconSize: [24, 24], iconAnchor: [12, 12] });
  }

  if ($("overview-map") && window.ADMIN_POINTS) {
    const map = baseMap("overview-map");
    for (const p of window.ADMIN_POINTS) {
      L.marker([p.lat, p.lng], { icon: pin(p.active ? "pin-answer" : "pin-answer pin-off"), title: p.title })
        .bindTooltip(p.title)
        .on("click", () => {
          const card = document.getElementById("q-" + p.id);
          if (card) {
            card.scrollIntoView({ behavior: "smooth", block: "center" });
            card.style.outline = "2px solid var(--accent)";
            setTimeout(() => (card.style.outline = ""), 1500);
          }
        })
        .addTo(map);
    }
    if (window.ADMIN_POINTS.length) {
      const bounds = L.latLngBounds(window.ADMIN_POINTS.map((p) => [p.lat, p.lng]));
      keepFitted(map, () => map.fitBounds(bounds, { padding: [30, 30], maxZoom: 7, animate: false }));
    }
  }

  const form = $("question-form");
  if (!form) return;

  const latInput = $("lat");
  const lngInput = $("lng");
  const map = baseMap("picker-map");
  let marker = null;

  function setPoint(latlng, { pan = false } = {}) {
    const ll = L.latLng(latlng);
    if (!marker) {
      marker = L.marker(ll, { icon: pin("pin-answer"), draggable: true }).addTo(map);
      marker.on("dragend", () => writeInputs(marker.getLatLng()));
    } else {
      marker.setLatLng(ll);
    }
    writeInputs(ll);
    if (pan) map.setView(ll, Math.max(map.getZoom(), 7));
  }

  function writeInputs(ll) {
    latInput.value = ll.lat.toFixed(5);
    lngInput.value = ll.lng.toFixed(5);
  }

  if (latInput.value && lngInput.value) setPoint([+latInput.value, +lngInput.value]);
  keepFitted(map, () => (marker ? map.setView(marker.getLatLng(), 6, { animate: false }) : map.fitBounds(EUROPE, { animate: false })));
  map.on("click", (e) => setPoint(e.latlng));
  for (const input of [latInput, lngInput]) {
    input.addEventListener("change", () => {
      const lat = parseFloat(latInput.value), lng = parseFloat(lngInput.value);
      if (Number.isFinite(lat) && Number.isFinite(lng)) setPoint([lat, lng], { pan: true });
    });
  }

  const geoQ = $("geo-q");
  const geoResults = $("geo-results");
  let geoTimer = null;
  let geoAbort = null;

  async function geocode(q) {
    geoAbort?.abort();
    geoAbort = new AbortController();
    const url = "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({
      q, format: "jsonv2", limit: "6", addressdetails: "1", "accept-language": "pl",
    });
    try {
      const res = await fetch(url, { signal: geoAbort.signal });
      renderGeo(await res.json());
    } catch (e) {
      if (e.name !== "AbortError") renderGeo([]);
    }
  }

  function placeLabel(r) {
    const a = r.address || {};
    const country = a.country;
    const name = r.name || r.display_name.split(",")[0];
    return country && country !== name ? `${name}, ${country}` : name;
  }

  function renderGeo(results) {
    geoResults.innerHTML = "";
    if (!results.length) {
      geoResults.innerHTML = '<li class="muted">Brak wyników</li>';
    }
    for (const r of results) {
      const li = document.createElement("li");
      li.textContent = r.display_name;
      li.addEventListener("click", () => pickGeo(r));
      geoResults.appendChild(li);
    }
    geoResults.hidden = false;
  }

  function pickGeo(r) {
    setPoint([+r.lat, +r.lon]);
    map.setView([+r.lat, +r.lon], 8);
    const nameInput = $("location-name");
    if (!nameInput.value) nameInput.value = placeLabel(r);
    geoResults.hidden = true;
    geoQ.value = "";
  }

  geoQ.addEventListener("input", () => {
    clearTimeout(geoTimer);
    const q = geoQ.value.trim();
    if (q.length < 3) { geoResults.hidden = true; return; }
    geoTimer = setTimeout(() => geocode(q), 400);
  });
  geoQ.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const first = geoResults.querySelector("li");
      if (!geoResults.hidden && first && !first.classList.contains("muted")) first.click();
      else if (geoQ.value.trim()) geocode(geoQ.value.trim());
    }
    if (e.key === "Escape") geoResults.hidden = true;
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".geo-search")) geoResults.hidden = true;
  });

  const AREA_STYLE = { color: "#704214", weight: 2, fillColor: "#D08C60", fillOpacity: 0.18 };
  const NOMINATIM_LEVEL = {

    miasto: { featureType: "city", threshold: "0.0005" },
    powiat: { featureType: "", threshold: "0.002" },
    region: { featureType: "state", threshold: "0.005" },
    panstwo: { featureType: "country", threshold: "0.01" },
  };
  const areaInput = $("area-geojson");
  const areaStatus = $("area-status");
  const areaResults = $("area-results");
  const areaLayer = L.geoJSON(null, { style: AREA_STYLE, interactive: false }).addTo(map);
  let areaParts = [];

  const level = () => form.querySelector('[name="area_level"]:checked').value;

  function showArea(geojson, { fit = true } = {}) {
    areaLayer.clearLayers();
    if (geojson) areaLayer.addData(geojson);
    if (fit && geojson && areaLayer.getBounds().isValid()) map.fitBounds(areaLayer.getBounds(), { padding: [20, 20] });
  }

  function setNewArea(parts, label) {
    areaParts = parts;
    const geo = { type: "GeometryCollection", geometries: parts };
    areaInput.value = parts.length ? JSON.stringify(geo) : "";
    $("area-clear").value = parts.length ? "" : "1";
    showArea(parts.length ? geo : null);
    areaStatus.textContent = parts.length ? `Nowa granica: ${label} (zapisze się po kliknięciu „Zapisz”).` : "Obszar zostanie usunięty po zapisie.";
  }

  function updateLevelUi() {
    const isPoint = level() === "punkt";
    $("area-tools").hidden = isPoint;
    $("level-hint").textContent = isPoint
      ? "Odległość liczona do punktu na mapie."
      : "Kliknięcie wewnątrz obszaru = pełne punkty, poza nim liczy się odległość do granicy.";
  }

  async function findArea() {
    const q = ($("geo-q").value || $("location-name").value || "").trim();
    if (!q) { areaStatus.textContent = "Wpisz nazwę w wyszukiwarkę nad mapą albo w „Nazwa miejsca”."; return; }
    const cfg = NOMINATIM_LEVEL[level()];
    const params = new URLSearchParams({
      q, format: "jsonv2", limit: "6", polygon_geojson: "1", polygon_threshold: cfg.threshold,
      addressdetails: "1", "accept-language": "pl",
    });
    if (cfg.featureType) params.set("featureType", cfg.featureType);
    areaStatus.textContent = `Szukam granicy: „${q}”…`;
    try {
      const res = await fetch("https://nominatim.openstreetmap.org/search?" + params);
      const found = (await res.json()).filter((r) => r.geojson && /Polygon/.test(r.geojson.type));
      areaResults.innerHTML = "";
      areaStatus.textContent = found.length ? "Wybierz właściwą granicę:" : "Nie znaleziono granicy. Spróbuj innej nazwy lub innego poziomu.";
      for (const r of found) {
        const li = document.createElement("li");
        li.textContent = `${r.display_name} (${r.addresstype || r.type})`;
        li.addEventListener("click", () => pickArea(r));
        li.addEventListener("mouseenter", () => showArea(r.geojson, { fit: false }));
        areaResults.appendChild(li);
      }
      areaResults.hidden = !found.length;
    } catch {
      areaStatus.textContent = "Nie udało się połączyć z Nominatim.";
    }
  }

  function pickArea(r) {
    areaResults.hidden = true;
    const parts = $("area-append").checked ? [...areaParts, r.geojson] : [r.geojson];
    setNewArea(parts, parts.length > 1 ? `${parts.length} części` : r.display_name);
    if (!latInput.value) setPoint([+r.lat, +r.lon]);
    const nameInput = $("location-name");
    if (!nameInput.value) nameInput.value = placeLabel(r);
  }

  $("find-area").addEventListener("click", findArea);
  $("clear-area").addEventListener("click", () => setNewArea([], ""));
  $("apply-paste").addEventListener("click", () => {
    try {
      const geo = JSON.parse($("area-paste").value);
      const geometry = geo.type === "Feature" ? geo.geometry : geo;
      setNewArea($("area-append").checked ? [...areaParts, geometry] : [geometry], "wklejony GeoJSON");
    } catch {
      areaStatus.textContent = "To nie jest poprawny JSON.";
    }
  });
  for (const radio of form.querySelectorAll('[name="area_level"]')) radio.addEventListener("change", updateLevelUi);
  areaResults.addEventListener("mouseleave", () => showArea(areaParts.length ? { type: "GeometryCollection", geometries: areaParts } : window.AREA, { fit: false }));

  if (areaInput.value) {
    try { setNewArea(JSON.parse(areaInput.value).geometries || [], "z poprzedniej próby zapisu"); } catch {  }
  } else if (window.AREA) {
    showArea(window.AREA);
    areaStatus.textContent = "Obecna granica jest zapisana. Możesz ją podmienić.";
  }
  updateLevelUi();

  const fileInput = $("image-file");
  const dropzone = $("dropzone");
  const preview = $("preview");
  const urlInput = $("image-url");

  function showPreview(src) {
    preview.src = src;
    preview.hidden = !src;
    $("drop-hint").hidden = !!src;
  }

  function useFile(file) {
    if (!file || !file.type.startsWith("image/")) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    urlInput.value = "";
    showPreview(URL.createObjectURL(file));
  }

  if (preview.getAttribute("src")) $("drop-hint").hidden = true;
  fileInput.addEventListener("change", () => fileInput.files[0] && useFile(fileInput.files[0]));
  for (const ev of ["dragenter", "dragover"]) {
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); });
  }
  for (const ev of ["dragleave", "drop"]) {
    dropzone.addEventListener(ev, () => dropzone.classList.remove("over"));
  }
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) return useFile(file);

    const url = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain");
    if (/^https?:\/\//.test(url)) { urlInput.value = url.trim(); fileInput.value = ""; showPreview(url.trim()); }
  });

  document.addEventListener("paste", (e) => {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (!item) return;
    e.preventDefault();
    const blob = item.getAsFile();
    const ext = blob.type.split("/")[1] || "png";
    useFile(new File([blob], `wklejone.${ext}`, { type: blob.type }));
  });
  urlInput.addEventListener("input", () => {
    const url = urlInput.value.trim();
    if (/^https?:\/\//.test(url)) { fileInput.value = ""; showPreview(url); }
  });

  const factsEditor = $("facts-editor");
  const factTpl = $("fact-row-tpl");
  function addFact(label = "", focus = true) {
    const row = factTpl.content.firstElementChild.cloneNode(true);
    row.querySelector('[name="fact_label"]').value = label;
    factsEditor.appendChild(row);
    if (focus) row.querySelector(label ? '[name="fact_value"]' : '[name="fact_label"]').focus();
  }
  $("add-fact").addEventListener("click", () => addFact());
  function insertPresets(focus) {
    const existing = new Set([...factsEditor.querySelectorAll('[name="fact_label"]')].map((i) => i.value.trim()));
    const labels = (window.FACT_PRESETS[$("category").value] || []).filter((l) => !existing.has(l));
    labels.forEach((l, i) => addFact(l, focus && i === 0));
  }
  $("preset-facts").addEventListener("click", () => insertPresets(true));
  factsEditor.addEventListener("click", (e) => {
    if (e.target.closest("[data-remove-fact]")) e.target.closest(".fact-row").remove();
  });
  if (!factsEditor.children.length) insertPresets(false);

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      form.requestSubmit(form.querySelector('button[value="list"]'));
    }
  });
})();
