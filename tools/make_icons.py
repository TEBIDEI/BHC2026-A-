"""Generuje ikony PWA w app/static/icons/ (uruchom raz: python tools/make_icons.py)."""
from pathlib import Path

from PIL import Image, ImageDraw

INK = "#3E2C1C"
PRIMARY = "#704214"
ACCENT = "#D08C60"
BG = "#F4ECD8"
OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
SS = 4  # supersampling dla gładkich krawędzi


def draw_icon(size, maskable=False):
    s = size * SS
    img = Image.new("RGB", (s, s), INK)
    d = ImageDraw.Draw(img)
    # Ikona maskable musi mieścić treść w środkowych 80%.
    scale = 0.62 if maskable else 0.78
    r = s * scale / 2
    cx = cy = s / 2
    # Pinezka: koło w kolorze primary z jasnym środkiem + kolor akcentu.
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PRIMARY)
    ri = r * 0.62
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=ACCENT)
    rc = r * 0.24
    d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=BG)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192).save(OUT / "icon-192.png")
    draw_icon(512).save(OUT / "icon-512.png")
    draw_icon(512, maskable=True).save(OUT / "icon-maskable-512.png")
    draw_icon(180).save(OUT / "apple-touch-icon.png")
    print("Ikony zapisane w", OUT)


if __name__ == "__main__":
    main()
