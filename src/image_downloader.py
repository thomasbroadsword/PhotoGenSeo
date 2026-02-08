"""
Pobieranie zdjęć z URL-i do katalogu lokalnego.
Deduplikacja po URL; zapis z bezpieczną nazwą pliku.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

import config

logger = logging.getLogger(__name__)

# dozwolone rozszerzenia / content-type
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif",
}
TIMEOUT = 15.0
MAX_SIZE_MB = 10


def _safe_filename(url: str, index: int) -> str:
    ext = ".jpg"
    try:
        path = url.split("?")[0]
        if path.lower().endswith(".png"):
            ext = ".png"
        elif path.lower().endswith(".webp"):
            ext = ".webp"
        elif path.lower().endswith(".gif"):
            ext = ".gif"
    except Exception:
        pass
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    safe = re.sub(r"[^\w\-]", "_", h)
    return f"{index:03d}_{safe}{ext}"


def download_image(
    url: str,
    dest_dir: Path,
    index: int = 0,
    client: Optional[httpx.Client] = None,
) -> Path | None:
    """
    Pobiera jeden obraz pod dest_dir. Zwraca ścieżkę pliku lub None przy błędzie.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / _safe_filename(url, index)

    if path.exists():
        return path

    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)

    try:
        r = client.get(url)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
        if ct not in ALLOWED_CONTENT_TYPES and not ct.startswith("image/"):
            logger.debug("Skip non-image content-type: %s", ct)
            return None
        size = len(r.content)
        if size > MAX_SIZE_MB * 1024 * 1024:
            logger.debug("Skip too large image: %s bytes", size)
            return None
        path.write_bytes(r.content)
        return path
    except Exception as e:
        logger.debug("Download failed %s: %s", url[:60], e)
        return None
    finally:
        if own_client and client:
            client.close()


def download_sources(
    image_urls: list[str],
    subdir: str | Path,
) -> list[Path]:
    """
    Pobiera listę URL-i do katalogu DATA/images/{subdir}.
    Zwraca listę ścieżek do pomyślnie zapisanych plików.
    """
    base = config.IMAGES_DIR / Path(subdir)
    return download_sources_to_dir(image_urls, base)


def download_sources_to_dir(image_urls: list[str], dest_dir: Path) -> list[Path]:
    """
    Pobiera listę URL-i do podanego katalogu (np. /tmp dla serverless).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        for i, url in enumerate(image_urls):
            p = download_image(url, dest_dir, index=i, client=client)
            if p is not None:
                paths.append(p)
    return paths
