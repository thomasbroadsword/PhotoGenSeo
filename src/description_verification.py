"""
Weryfikacja opisu produktu oraz ekstrakcja wiarygodnych danych: EAN, wymiary (gdy widoczne na zdjęciach).
Claude analizuje zdjęcia i zwraca zweryfikowany opis + pola strukturalne.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import config
from src.claude_client import message_with_images

logger = logging.getLogger(__name__)

SYSTEM_VERIFY = """Jesteś asystentem weryfikującym opisy produktów na podstawie zdjęć.
Twoje zadania:
1) Zweryfikować podany opis produktu – czy zgadza się z tym, co widać na zdjęciach (np. kolor, kształt, opakowanie, zawartość).
2) Z zebranych zdjęć wyciągnąć WIARYGODNE dane, które są WIDOCZNE na zdjęciach:
   - EAN / kod kreskowy – tylko jeśli wyraźnie czytelny na zdjęciu (podaj dokładnie)
   - Wymiary – tylko jeśli widoczne na opakowaniu/etykiecie (np. "120x80x40 mm", "500 ml")
   - Inne dane z etykiety (skład, waga) – tylko jeśli czytelne
3) Nie wymyślaj danych – jeśli czegoś nie widać, wpisz null.
4) Język wyników: {lang}.

Odpowiedz WYŁĄCZNIE poprawnym JSON (bez markdown):
{{
  "description_verified": "zweryfikowany, poprawiony opis produktu (pełny tekst)",
  "description_confidence": 0.9,
  "ean_from_images": "kod EAN jeśli czytelny na zdjęciu, else null",
  "dimensions_from_images": "wymiary jeśli widoczne, else null",
  "volume_or_weight_from_images": "np. 500ml / 250g jeśli widoczne, else null",
  "other_visible_data": {{ "klucz": "wartość z etykiety/opakowania" }},
  "corrections_made": ["lista wprowadzonych poprawek do opisu"]
}}"""

USER_VERIFY_TEMPLATE = """Produkt (nazwa): {product_name}
Oryginalny opis do weryfikacji:
---
{original_description}
---

Przeanalizuj załączone zdjęcia i:
1) Zweryfikuj/popraw opis.
2) Wypisz EAN, wymiary, objętość/wagę TYLKO jeśli wyraźnie widać na zdjęciach.
3) Język wyników: {lang}.

Odpowiedz tylko JSON."""


def _parse_verify_response(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def verify_description_and_extract_data(
    image_paths: list[Path],
    product_name: str,
    original_description: str,
    lang: str | None = None,
) -> dict[str, Any]:
    """
    Na podstawie zdjęć weryfikuje opis i wyciąga EAN, wymiary itd. gdy widoczne.
    Zwraca słownik z: description_verified, ean_from_images, dimensions_from_images, itd.
    """
    lang = lang or config.OUTPUT_LANG
    system = SYSTEM_VERIFY.format(lang=lang)
    user = USER_VERIFY_TEMPLATE.format(
        product_name=product_name,
        original_description=original_description or "(brak opisu)",
        lang=lang,
    )
    # nie wysyłaj zbyt wielu zdjęć naraz
    batch = image_paths[: config.MAX_IMAGES_TO_ANALYZE]
    try:
        response = message_with_images(system, user, batch, max_tokens=4096)
    except Exception as e:
        logger.warning("Description verification API error: %s", e)
        return {
            "description_verified": original_description,
            "description_confidence": 0.0,
            "ean_from_images": None,
            "dimensions_from_images": None,
            "volume_or_weight_from_images": None,
            "other_visible_data": {},
            "corrections_made": [],
            "error": str(e),
        }

    parsed = _parse_verify_response(response)
    if not parsed:
        return {
            "description_verified": original_description,
            "description_confidence": 0.0,
            "ean_from_images": None,
            "dimensions_from_images": None,
            "volume_or_weight_from_images": None,
            "other_visible_data": {},
            "corrections_made": [],
        }
    return {
        "description_verified": parsed.get("description_verified") or original_description,
        "description_confidence": float(parsed.get("description_confidence", 0)),
        "ean_from_images": parsed.get("ean_from_images"),
        "dimensions_from_images": parsed.get("dimensions_from_images"),
        "volume_or_weight_from_images": parsed.get("volume_or_weight_from_images"),
        "other_visible_data": parsed.get("other_visible_data") or {},
        "corrections_made": parsed.get("corrections_made") or [],
    }
