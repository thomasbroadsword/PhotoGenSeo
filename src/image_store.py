"""
Pomniejszanie zdjęć do zapisu w bazie (tylko te wykorzystane w pipeline).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

import config

logger = logging.getLogger(__name__)


def resize_image_for_storage(
    path: Path | str,
    max_px: Optional[int] = None,
    quality: Optional[int] = None,
) -> tuple[bytes, str, int, int]:
    """
    Czyta obraz z dysku, pomniejsza (z zachowaniem proporcji) i zwraca (bytes, content_type, width, height).

    max_px: maksymalna długość dłuższego boku (domyślnie z config).
    quality: jakość JPEG 1–100 (domyślnie z config).
    Zawsze zwraca JPEG (content_type image/jpeg) dla mniejszego rozmiaru.
    """
    path = Path(path)
    max_px = max_px or config.IMAGE_STORE_MAX_PX
    quality = quality or config.IMAGE_STORE_QUALITY
    if not path.exists():
        raise FileNotFoundError(str(path))
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > max_px or h > max_px:
        if w >= h:
            new_w, new_h = max_px, int(h * max_px / w)
        else:
            new_w, new_h = int(w * max_px / h), max_px
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        w, h = img.size
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg", w, h
