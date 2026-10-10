import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}


class UploadError(ValueError):
    pass


def save_image(file_storage):
    ext = Path(file_storage.filename or "").suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise UploadError(f"Nieobsługiwany format pliku: {ext}")
    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError):
        raise UploadError("Plik nie jest poprawnym obrazkiem.")

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    side = current_app.config["MAX_IMAGE_SIDE"]
    img.thumbnail((side, side))

    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.webp"
    img.save(upload_dir / name, "WEBP", quality=85)
    return name


def delete_image(filename):
    if not filename:
        return
    path = Path(current_app.config["UPLOAD_DIR"]) / filename
    path.unlink(missing_ok=True)
