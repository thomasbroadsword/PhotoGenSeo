"""
Wyszukiwanie źródeł zdjęć i stron produktu.

Priorytet: SerpAPI (Google Images + Google Search) → fallback DuckDuckGo Images.
Każde źródło ma URL obrazu, URL strony (jeśli znany) i metadane do późniejszej oceny wiarygodności.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)


@dataclass
class ImageSource:
    """Pojedyncze źródło: URL obrazu + opcjonalnie strona (do oceny wiarygodności)."""
    image_url: str
    page_url: str | None = None
    title: str | None = None
    source_domain: str | None = None  # domena strony (np. sklep)
    width: int | None = None
    height: int | None = None
    # do późniejszej oceny przez Claude
    raw_serp_snippet: str | None = None

    def __post_init__(self) -> None:
        if self.page_url and not self.source_domain:
            try:
                self.source_domain = urlparse(self.page_url).netloc or None
            except Exception:
                pass


def _search_serpapi_images(query: str, count: int) -> list[ImageSource]:
    """SerpAPI – Google Images. Wymaga SERPAPI_API_KEY."""
    if not config.SERPAPI_API_KEY:
        return []
    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google_images",
            "q": query,
            "api_key": config.SERPAPI_API_KEY,
            "num": min(count, 100),
            "hl": "pl",
            "gl": "pl",
        }
        search = GoogleSearch(params)
        data = search.get_dict()
        out: list[ImageSource] = []
        for obj in data.get("images_results", [])[:count]:
            img_url = obj.get("original") or obj.get("image") or obj.get("thumbnail")
            if not img_url:
                continue
            link = obj.get("link")  # strona, z której pochodzi obraz
            out.append(ImageSource(
                image_url=img_url,
                page_url=link,
                title=obj.get("title"),
                source_domain=urlparse(link).netloc if link else None,
                width=obj.get("original_width"),
                height=obj.get("original_height"),
                raw_serp_snippet=obj.get("title") or "",
            ))
        return out
    except Exception as e:
        logger.warning("SerpAPI Google Images failed: %s", e)
        return []


def _search_serpapi_organic(query: str, count: int) -> list[dict[str, Any]]:
    """SerpAPI – zwykłe wyniki Google (strony). Przydatne do oceny źródeł / kontekstu."""
    if not config.SERPAPI_API_KEY:
        return []
    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google",
            "q": query,
            "api_key": config.SERPAPI_API_KEY,
            "num": min(count, 20),
            "hl": "pl",
            "gl": "pl",
        }
        search = GoogleSearch(params)
        data = search.get_dict()
        return data.get("organic_results", [])[:count]
    except Exception as e:
        logger.warning("SerpAPI Google organic failed: %s", e)
        return []


def _search_duckduckgo_images(query: str, count: int) -> list[ImageSource]:
    """Fallback: DuckDuckGo Images (bez klucza API)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=count))
        out: list[ImageSource] = []
        for r in results:
            img_url = r.get("image") or r.get("url")
            if not img_url:
                continue
            out.append(ImageSource(
                image_url=img_url,
                page_url=r.get("url"),
                title=r.get("title"),
                source_domain=urlparse(r["url"]).netloc if r.get("url") else None,
                raw_serp_snippet=r.get("title") or "",
            ))
        return out
    except Exception as e:
        logger.warning("DuckDuckGo images failed: %s", e)
        return []


def search_image_sources(
    product_name: str,
    ean: str | None = None,
    min_count: int | None = None,
) -> tuple[list[ImageSource], list[dict[str, Any]]]:
    """
    Wyszukuje źródła zdjęć (min. min_count) oraz wyniki Google (organic) do oceny kontekstu.

    Zapytanie: product_name + opcjonalnie EAN. Zwraca (lista ImageSource, lista wyników Google).
    """
    min_count = min_count or config.MIN_IMAGES_TO_FETCH
    query = f"{product_name}"
    if ean:
        query = f"{product_name} {ean}"

    sources: list[ImageSource] = []
    seen_urls: set[str] = set()

    # 1) SerpAPI Google Images
    serp_sources = _search_serpapi_images(query, min_count * 2)
    for s in serp_sources:
        if s.image_url not in seen_urls:
            seen_urls.add(s.image_url)
            sources.append(s)
    # 2) Fallback DuckDuckGo
    if len(sources) < min_count:
        ddg = _search_duckduckgo_images(query, min_count * 2)
        for s in ddg:
            if s.image_url not in seen_urls:
                seen_urls.add(s.image_url)
                sources.append(s)

    # Wyniki Google (organic) – do weryfikacji źródeł / „na koniec wyniki Google”
    organic = _search_serpapi_organic(query, 10)

    return sources[: min_count * 2], organic  # zwracamy więcej niż min_count, potem filtrowanie
