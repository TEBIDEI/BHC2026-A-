(() => {
  "use strict";

  const MAX_SCALE = 8;
  const box = document.getElementById("lightbox");
  if (!box) return;
  const stage = box.querySelector(".zoom-stage");
  const img = box.querySelector(".zoom-stage img");
  const level = box.querySelector(".zoom-level");

  let base = { w: 0, h: 0 };
  let s = 1, x = 0, y = 0;
  let moved = false;
  const pointers = new Map();
  let pinch = null;

  const hiRes = (url) => (url || "").replace(/([?&]width=)\d+/, "$12560");

  function fit() {
    const sw = stage.clientWidth, sh = stage.clientHeight;
    const ratio = (img.naturalWidth || 4) / (img.naturalHeight || 3);
    base = sw / sh > ratio ? { w: sh * ratio, h: sh } : { w: sw, h: sw / ratio };
    img.style.width = base.w + "px";
    img.style.height = base.h + "px";
  }

  function clamp() {
    const sw = stage.clientWidth, sh = stage.clientHeight;
    const w = base.w * s, h = base.h * s;
    x = w <= sw ? (sw - w) / 2 : Math.min(0, Math.max(sw - w, x));
    y = h <= sh ? (sh - h) / 2 : Math.min(0, Math.max(sh - h, y));
  }

  function render() {
    clamp();
    img.style.transform = `translate(${x}px, ${y}px) scale(${s})`;
    level.textContent = Math.round(s * 100) + "%";
    stage.classList.toggle("zoomed", s > 1.01);
  }

  function zoomAt(px, py, factor) {
    const next = Math.min(MAX_SCALE, Math.max(1, s * factor));
    x = px - (px - x) * (next / s);
    y = py - (py - y) * (next / s);
    s = next;
    render();
  }

  function centre() {
    return [stage.clientWidth / 2, stage.clientHeight / 2];
  }

  function local(e) {
    const r = stage.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function reset() {
    s = 1;
    fit();
    render();
  }

  let opened = 0;

  function open(src) {
    if (!src) return;
    const token = ++opened;
    box.hidden = false;
    document.body.classList.add("no-scroll");
    img.onload = reset;
    img.src = src;
    const big = hiRes(src);
    if (big !== src) {
      const pre = new Image();
      pre.onload = () => {
        if (box.hidden || token !== opened) return;
        img.onload = () => { fit(); render(); };
        img.src = big;
      };
      pre.src = big;
    }
    reset();
    box.querySelector('[data-zoom="close"]').focus({ preventScroll: true });
  }

  function close() {
    box.hidden = true;
    document.body.classList.remove("no-scroll");
    pointers.clear();
    pinch = null;
  }

  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomAt(...local(e), Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });

  stage.addEventListener("dblclick", (e) => {
    if (s > 1.5) reset();
    else zoomAt(...local(e), 2.5);
  });

  stage.addEventListener("pointerdown", (e) => {
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, local(e));
    moved = false;
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { dist: Math.hypot(a[0] - b[0], a[1] - b[1]), scale: s };
    }
  });

  stage.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) return;
    const prev = pointers.get(e.pointerId);
    const now = local(e);
    pointers.set(e.pointerId, now);
    if (pointers.size === 2 && pinch) {
      const [a, b] = [...pointers.values()];
      const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
      const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      zoomAt(mid[0], mid[1], (pinch.scale * dist / pinch.dist) / s);
      moved = true;
    } else if (pointers.size === 1 && s > 1) {
      x += now[0] - prev[0];
      y += now[1] - prev[1];
      if (Math.abs(now[0] - prev[0]) + Math.abs(now[1] - prev[1]) > 1) moved = true;
      render();
    }
  });

  const release = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
  };
  stage.addEventListener("pointerup", release);
  stage.addEventListener("pointercancel", release);

  stage.addEventListener("click", (e) => {
    if (!moved && s <= 1.01 && e.target === stage) close();
  });

  box.addEventListener("click", (e) => {
    const action = e.target.closest("[data-zoom]")?.dataset.zoom;
    if (action === "in") zoomAt(...centre(), 1.5);
    else if (action === "out") zoomAt(...centre(), 1 / 1.5);
    else if (action === "reset") reset();
    else if (action === "close") close();
  });

  document.addEventListener("keydown", (e) => {
    if (box.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "+" || e.key === "=") zoomAt(...centre(), 1.5);
    else if (e.key === "-") zoomAt(...centre(), 1 / 1.5);
    else if (e.key === "0") reset();
    else return;
    e.preventDefault();
    e.stopPropagation();
  }, true);

  window.addEventListener("resize", () => { if (!box.hidden) reset(); });

  window.openZoom = open;
})();
