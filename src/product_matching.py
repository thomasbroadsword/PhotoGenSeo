"""
AI matching produktów: Claude ocenia, czy zdjęcia przedstawiają ten sam produkt (ten sam EAN).
Odrzucane są zdjęcia innego produktu lub budzące wątpliwość.
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

SYSTEM_MATCHING = """Jesteś asystentem weryfikującym zdjęcia produktów.
Otrzymujesz zdjęcia ponumerowane (1, 2, 3, ...) oraz nazwę produktu i opcjonalnie kod EAN.
Twoje zadanie: ocenić, czy każde zdjęcie przedstawia TEN SAM produkt (ten sam artykuł, ten sam EAN).
Uwzględnij: ten sam opakowanie/wygląd, ten sam produkt wewnątrz, ten sam kod kreskowy jeśli widoczny.
Odrzuć zdjęcia: innego produktu, mockupu, tylko logo, tylko tekst, nieczytelne, z innego opakowania (np. inna pojemność).
Odpowiedz WYŁĄCZNIE poprawnym JSON (bez markdown, bez ```), w formacie:
{"matches": [{"index": 1, "same_product": true, "confidence": 0.95, "reason": "krótki powód"}, ...], "overall_confidence": 0.9}
- index: numer zdjęcia (1-based)
- same_product: czy to ten sam produkt
- confidence: 0-1 pewność
- reason: krótkie uzasadnienie
- overall_confidence: 0-1 średnia pewność dla zdjęć uznanych za ten sam produkt."""

USER_MATCHING_TEMPLATE = """Produkt: {product_name}
EAN: {ean}

Zdjęcia są ponumerowane w kolejności załączników (pierwsze zdjęcie = 1, drugie = 2, itd.).
Dla każdego zdjęcia podaj: czy to ten sam produkt (same_product), confidence 0-1 i krótki reason.
Odpowiedz tylko JSON."""


def _parse_matching_response(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    # usuń ewentualny markdown
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def filter_matching_images(
    image_paths: list[Path],
    product_name: str,
    ean: str | None = None,
) -> tuple[list[Path], list[Path], dict[str, Any]]:
    """
    Claude ocenia każde zdjęcie: ten sam produkt czy nie.
    Zwraca: (ścieżki zdjęć uznanych za ten sam produkt, odrzucone, surowa odpowiedź JSON).
    """
    if not image_paths:
        return [], [], {}

    ean = ean or "nie podano"
    user = USER_MATCHING_TEMPLATE.format(product_name=product_name, ean=ean)
    # Limit zdjęć w jednym wywołaniu (kontekst)
    batch_size = 10
    accepted: list[Path] = []
    rejected: list[Path] = []
    all_parsed: list[dict[str, Any]] = []

    for start in range(0, len(image_paths), batch_size):
        batch = image_paths[start : start + batch_size]
        try:
            response = message_with_images(SYSTEM_MATCHING, user, batch, max_tokens=2048)
        except Exception as e:
            logger.warning("Product matching API error: %s", e)
            # w razie błędu zostawiamy wszystkie w batchu jako zaakceptowane
            accepted.extend(batch)
            continue

        parsed = _parse_matching_response(response)
        if not parsed:
            accepted.extend(batch)
            continue

        matches = parsed.get("matches") or []
        min_conf = config.PRODUCT_MATCH_MIN_CONFIDENCE
        for i, path in enumerate(batch):
            idx_1based = start + i + 1
            item = next((m for m in matches if m.get("index") == idx_1based), None)
            if not item:
                accepted.append(path)
                continue
            same = item.get("same_product", True)
            conf = float(item.get("confidence", 0.5))
            if same and conf >= min_conf:
                accepted.append(path)
            else:
                rejected.append(path)
        all_parsed.append(parsed)

    return accepted, rejected, {"batches": all_parsed}
