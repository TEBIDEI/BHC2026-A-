import io
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import StoredImage, db

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

    buffer = io.BytesIO()
    img.save(buffer, "WEBP", quality=85)
    name = f"{uuid.uuid4().hex}.webp"
    db.session.add(StoredImage(name=name, mime="image/webp", data=buffer.getvalue()))
    return name


def delete_image(name):
    if not name:
        return
    for obj in list(db.session.new):
        if isinstance(obj, StoredImage) and obj.name == name:
            db.session.expunge(obj)
            return
    with db.session.no_autoflush:
        stored = db.session.get(StoredImage, name)
    if stored:
        db.session.delete(stored)
    legacy = Path(current_app.config["UPLOAD_DIR"]) / name
    legacy.unlink(missing_ok=True)
