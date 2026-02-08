"""
Odrzucanie wątpliwych źródeł i zdjęć niewnoszących nic do unikalności opisu.
Claude ocenia: wiarygodność źródła (na podstawie domeny/kontekstu) oraz
czy zdjęcie wnosi coś unikalnego (np. inny kąt, opakowanie, etykieta) czy jest duplikatem/mockupem.
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

SYSTEM_QUALITY = """Jesteś asystentem oceniającym źródła i zdjęcia produktów pod kątem budowania unikalnego opisu SEO.
Dla każdego zdjęcia (ponumerowanego) oceniasz:
1) Czy zdjęcie wnosi coś UNIKALNEGO do opisu (np. nowy kąt, opakowanie, etykieta, skład, wymiary na zdjęciu) – czy to duplikat / to samo co inne / mockup / stock?
2) Czy źródło (domena/strona) budzi zaufanie (sklep, producent, serwis porównawczy) czy wątpliwe (spam, nieznana strona)?

Odrzuć zdjęcia: duplikaty treściowo, same mockupy, bez wartości informacyjnej, z bardzo wątpliwych źródeł.
Odpowiedz WYŁĄCZNIE poprawnym JSON (bez markdown):
{"images": [{"index": 1, "uniqueness_score": 0.8, "source_trust_score": 0.7, "keep": true, "reason": "krótki powód"}, ...]}
- uniqueness_score: 0-1 (jak bardzo zdjęcie wnosi coś unikalnego)
- source_trust_score: 0-1 (wiarygodność źródła)
- keep: true jeśli warto zostawić do opisu
- reason: krótkie uzasadnienie"""

USER_QUALITY_TEMPLATE = """Produkt: {product_name}
Zdjęcia są ponumerowane w kolejności załączników (1, 2, 3, ...).
Dla każdego zdjęcia: uniqueness_score, source_trust_score, keep (true/false), reason.
Źródła (jeśli znane): {sources_text}

Odpowiedz tylko JSON."""


def _parse_quality_response(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def filter_quality(
    image_paths: list[Path],
    product_name: str,
    source_domains: list[str] | None = None,
) -> tuple[list[Path], list[Path], dict[str, Any]]:
    """
    Claude ocenia unikalność i wiarygodność każdego zdjęcia.
    Zwraca: (ścieżki do zostawienia, odrzucone, surowa odpowiedź).
    """
    if not image_paths:
        return [], [], {}

    sources_text = ", ".join(source_domains[:20]) if source_domains else "nie podano"
    user = USER_QUALITY_TEMPLATE.format(
        product_name=product_name,
        sources_text=sources_text,
    )
    batch_size = 10
    keep_paths: list[Path] = []
    drop_paths: list[Path] = []
    all_parsed: list[dict[str, Any]] = []

    for start in range(0, len(image_paths), batch_size):
        batch = image_paths[start : start + batch_size]
        try:
            response = message_with_images(SYSTEM_QUALITY, user, batch, max_tokens=2048)
        except Exception as e:
            logger.warning("Quality filter API error: %s", e)
            keep_paths.extend(batch)
            continue

        parsed = _parse_quality_response(response)
        if not parsed:
            keep_paths.extend(batch)
            continue

        images = parsed.get("images") or []
        min_uniqueness = config.IMAGE_UNIQUENESS_MIN_SCORE
        min_trust = config.SOURCE_TRUST_MIN_SCORE
        for i, path in enumerate(batch):
            idx_1based = start + i + 1
            item = next((m for m in images if m.get("index") == idx_1based), None)
            if not item:
                keep_paths.append(path)
                continue
            keep = item.get("keep", True)
            u = float(item.get("uniqueness_score", 0.5))
            t = float(item.get("source_trust_score", 0.5))
            if keep and u >= min_uniqueness and t >= min_trust:
                keep_paths.append(path)
            else:
                drop_paths.append(path)
        all_parsed.append(parsed)

    return keep_paths, drop_paths, {"batches": all_parsed}
