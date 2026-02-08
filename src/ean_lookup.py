"""
Identyfikacja produktu po kodzie EAN: Open Food Facts (darmowe) + opcjonalnie EAN-DB (JWT).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
import config

logger = logging.getLogger(__name__)

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
EAN_DB_URL = "https://ean-db.com/api/v2/product/{barcode}"


@dataclass
class ProductInfo:
    name: str
    ean: str
    brand: str | None = None
    categories: list[str] | None = None
    image_url: str | None = None
    raw: dict[str, Any] | None = None


def _normalize_ean(barcode: str) -> str:
    return "".join(c for c in str(barcode).strip() if c.isdigit())


def lookup_openfoodfacts(ean: str) -> ProductInfo | None:
    """Open Food Facts – darmowe, bez klucza (gł. żywność)."""
    ean = _normalize_ean(ean)
    if not ean or len(ean) < 8:
        return None
    url = OPEN_FOOD_FACTS_URL.format(barcode=ean)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.debug("Open Food Facts lookup failed: %s", e)
        return None
    if data.get("status") != 1 or not data.get("product"):
        return None
    p = data["product"]
    name = (
        p.get("product_name") or p.get("product_name_pl") or p.get("product_name_en") or ""
    ).strip()
    if not name:
        name = p.get("brands") or "Produkt"
    return ProductInfo(
        name=name or f"Produkt {ean}",
        ean=ean,
        brand=p.get("brands"),
        categories=p.get("categories") and p["categories"].split(",")[:3] or None,
        image_url=p.get("image_url") or p.get("image_front_url"),
        raw=p,
    )


def lookup_ean_db(ean: str) -> ProductInfo | None:
    """EAN-DB – wymaga EAN_DB_JWT (Bearer)."""
    if not config.EAN_DB_JWT:
        return None
    ean = _normalize_ean(ean)
    if not ean:
        return None
    url = EAN_DB_URL.format(barcode=ean)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.EAN_DB_JWT}",
                    "Accept": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.debug("EAN-DB lookup failed: %s", e)
        return None
    prod = data.get("product")
    if not prod:
        return None
    titles = prod.get("titles") or {}
    name = titles.get("pl") or titles.get("en") or list(titles.values())[0] if titles else ""
    if not name and prod.get("manufacturer", {}).get("titles"):
        name = list(prod["manufacturer"]["titles"].values())[0]
    if not name:
        name = f"Produkt {ean}"
    images = prod.get("images") or []
    image_url = images[0]["url"] if images else None
    categories = []
    for c in prod.get("categories") or []:
        t = (c.get("titles") or {}).get("pl") or (c.get("titles") or {}).get("en")
        if t:
            categories.append(t)
    return ProductInfo(
        name=name,
        ean=prod.get("barcode") or ean,
        brand=(prod.get("manufacturer") or {}).get("titles", {}).get("en"),
        categories=categories[:5] or None,
        image_url=image_url,
        raw=prod,
    )


def lookup_product(ean: str) -> ProductInfo | None:
    """
    Identyfikacja produktu po EAN. Kolejność: EAN-DB (jeśli JWT) → Open Food Facts.
    """
    ean = _normalize_ean(ean)
    if not ean:
        return None
    info = lookup_ean_db(ean) if config.EAN_DB_JWT else None
    if not info:
        info = lookup_openfoodfacts(ean)
    if not info:
        return ProductInfo(name=f"Produkt EAN {ean}", ean=ean, raw=None)
    return info
