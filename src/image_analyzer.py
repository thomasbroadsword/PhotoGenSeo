"""
Analiza zdjęć przez Claude Vision – generowanie opisu bazowego (podstawa pod SEO).
"""
from __future__ import annotations

import logging
from pathlib import Path

import config
from src.claude_client import message_with_images

logger = logging.getLogger(__name__)

SYSTEM_ANALYZE = """Jesteś asystentem tworzącym opisy produktów na podstawie zdjęć.
Na podstawie załączonych zdjęć produktu napisz JEDEN spójny, szczegółowy opis produktu w języku polskim.
Opis ma być podstawą do późniejszej generacji opisu SEO (bogate w detale: wygląd, opakowanie, etykieta, zastosowanie).
Uwzględnij wszystko, co widać na zdjęciach: kształt, kolor, rozmiar względny, tekst z opakowania (skład, instrukcje), kod kreskowy jeśli widoczny.
Pisz w trzeciej osobie, neutralnie. Nie wymyślaj faktów – tylko to, co wynika ze zdjęć.
Długość: 2–4 akapity."""

USER_ANALYZE = """Wygeneruj opis produktu na podstawie załączonych zdjęć. Język: polski. Opis ma być podstawą pod przyszły opis SEO."""


def analyze_images_for_description(image_paths: list[Path]) -> str:
    """
    Claude analizuje zdjęcia i zwraca jeden opis bazowy (tekst).
    """
    if not image_paths:
        return ""
    batch = image_paths[: config.MAX_IMAGES_TO_ANALYZE]
    try:
        return message_with_images(SYSTEM_ANALYZE, USER_ANALYZE, batch, max_tokens=2048)
    except Exception as e:
        logger.warning("Image analysis API error: %s", e)
        return ""
