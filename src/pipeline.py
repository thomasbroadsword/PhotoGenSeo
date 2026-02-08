"""
Główny pipeline: EAN → źródła (SerpAPI/Google) → pobieranie → analiza kosztów →
AI matching → filtrowanie jakości → analiza zdjęć → weryfikacja opisu (EAN, wymiary) →
zapis do plików i do bazy (Vercel Postgres); w bazie tylko pomniejszone zdjęcia wykorzystane.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import config
from src.ean_lookup import lookup_product, ProductInfo
from src.source_search import search_image_sources, ImageSource
from src.image_downloader import download_sources
from src.cost_estimate import estimate_generation_cost
from src.product_matching import filter_matching_images
from src.quality_filter import filter_quality
from src.image_analyzer import analyze_images_for_description
from src.description_verification import verify_description_and_extract_data

logger = logging.getLogger(__name__)


def run_pipeline(
    ean: str,
    *,
    min_images: int | None = None,
    output_subdir: str | None = None,
    estimate_only: bool = False,
    save_to_db: bool = True,
) -> dict[str, Any]:
    """
    Pełny przebieg dla jednego EAN.

    1. Identyfikacja produktu po EAN
    2. Wyszukanie źródeł (SerpAPI Google Images + organic, fallback DuckDuckGo)
    3. Pobranie min. min_images zdjęć
    4. Analiza kosztów przed generowaniem (cost_estimate); opcjonalnie zapis runu do bazy
    5. Jeśli estimate_only=True – zwraca wynik z cost_estimate i (opcjonalnie) run_id, bez wywołań Claude
    6. AI matching → filtrowanie jakości → analiza zdjęć → weryfikacja opisu
    7. Zapis do data/output/ oraz do bazy (run + tylko pomniejszone zdjęcia wykorzystane)
    """
    min_images = min_images or config.MIN_IMAGES_TO_FETCH
    ean_clean = "".join(c for c in str(ean).strip() if c.isdigit())
    if not ean_clean:
        return {"error": "Invalid EAN", "ean": ean}

    out_dir = config.OUTPUT_DIR
    if output_subdir:
        out_dir = out_dir / output_subdir
    else:
        out_dir = out_dir / ean_clean
    out_dir.mkdir(parents=True, exist_ok=True)
    images_subdir = config.IMAGES_DIR / (output_subdir or ean_clean)
    images_subdir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "ean": ean_clean,
        "product": None,
        "sources_found": 0,
        "images_downloaded": 0,
        "after_matching": 0,
        "after_quality_filter": 0,
        "base_description": "",
        "verified": {},
        "organic_results": [],
        "output_dir": str(out_dir),
    }

    # 1) Lookup produktu
    product = lookup_product(ean_clean)
    result["product"] = {
        "name": product.name,
        "ean": product.ean,
        "brand": product.brand,
        "categories": product.categories,
    }
    logger.info("Product: %s (EAN %s)", product.name, product.ean)

    # 2) Źródła: SerpAPI (obrazy + organic) / DuckDuckGo
    sources, organic = search_image_sources(
        product.name,
        ean=product.ean,
        min_count=min_images,
    )
    result["sources_found"] = len(sources)
    result["organic_results"] = [
        {"title": o.get("title"), "link": o.get("link")} for o in organic[:10]
    ]
    if not sources:
        result["error"] = "No image sources found"
        _save_result(result, out_dir)
        return result

    urls = [s.image_url for s in sources]
    source_domains = [s.source_domain for s in sources if s.source_domain]

    # 3) Pobieranie
    paths = download_sources(urls, subdir=output_subdir or ean_clean)
    result["images_downloaded"] = len(paths)
    if not paths:
        result["error"] = "No images downloaded"
        _save_result(result, out_dir)
        return result

    # 4) Analiza kosztów przed generowaniem
    cost_estimate = estimate_generation_cost(len(paths))
    result["cost_estimate"] = cost_estimate
    run_id: str | None = None
    if save_to_db and config.POSTGRES_URL:
        try:
            from src.db import save_run
            run_id = save_run(
                ean_clean,
                product_name=product.name,
                cost_estimate=cost_estimate,
                result=None,
            )
            result["run_id"] = run_id
            logger.info("Cost estimate: ~%.4f USD (run_id=%s)", cost_estimate.get("estimated_usd", 0), run_id)
        except Exception as e:
            logger.warning("DB save run (cost estimate) failed: %s", e)
    else:
        logger.info("Cost estimate: ~%.4f USD", cost_estimate.get("estimated_usd", 0))

    if estimate_only:
        _save_result(result, out_dir)
        return result

    # 5) AI matching – ten sam produkt
    matched, rejected_match, _ = filter_matching_images(
        paths, product.name, product.ean
    )
    result["after_matching"] = len(matched)
    result["rejected_matching_count"] = len(rejected_match)
    if not matched:
        matched = paths  # fallback: zostaw wszystkie
        result["after_matching"] = len(matched)

    # 5) Jakość – odrzuć wątpliwe i niewnoszące unikalności
    keep, rejected_quality, _ = filter_quality(
        matched, product.name, source_domains=source_domains
    )
    result["after_quality_filter"] = len(keep)
    result["rejected_quality_count"] = len(rejected_quality)
    if not keep:
        keep = matched

    # 6) Opis bazowy z zdjęć
    base_desc = analyze_images_for_description(keep)
    result["base_description"] = base_desc

    # 7) Weryfikacja opisu + EAN, wymiary z zdjęć
    verified = verify_description_and_extract_data(
        keep,
        product.name,
        base_desc,
        lang=config.OUTPUT_LANG,
    )
    result["verified"] = verified

    # Zapis do bazy: aktualizacja runu (wynik) + tylko wykorzystane zdjęcia (pomniejszone)
    if save_to_db and config.POSTGRES_URL and run_id:
        try:
            from src.db import save_run, save_used_images
            save_run(ean_clean, result=result, run_id=run_id)
            # URL-e w tej samej kolejności co paths (paths[i] ↔ urls[i])
            path_to_index = {str(Path(p).resolve()): i for i, p in enumerate(paths)}
            source_urls_for_keep = [
                urls[path_to_index[str(Path(p).resolve())]] if str(Path(p).resolve()) in path_to_index else None
                for p in keep
            ]
            saved_count = save_used_images(run_id, ean_clean, keep, source_urls_for_keep)
            result["images_saved_to_db"] = saved_count
            logger.info("Saved %s used images to DB (run_id=%s)", saved_count, run_id)
        except Exception as e:
            logger.warning("DB save result/images failed: %s", e)

    _save_result(result, out_dir)
    return result


def run_pipeline_from_selected_images(
    ean: str,
    product_name: str,
    image_urls: list[str],
    uploaded_images_base64: list[str] | None = None,
    work_dir: Path | str | None = None,
    save_to_db: bool = False,
) -> dict[str, Any]:
    """
    Generuje opis na podstawie wybranych przez użytkownika zdjęć (bez wyszukiwania i AI matching).
    image_urls: lista URL-i do pobrania.
    uploaded_images_base64: opcjonalna lista base64 (data URL lub surowy base64) wgranych zdjęć.
    work_dir: katalog roboczy (np. /tmp dla serverless). Domyślnie IMAGES_DIR/ean.
    """
    import base64
    import uuid as _uuid
    ean_clean = "".join(c for c in str(ean).strip() if c.isdigit())
    if not ean_clean:
        return {"error": "Invalid EAN", "ean": ean}
    work_dir = Path(work_dir) if work_dir else config.IMAGES_DIR / ean_clean
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "ean": ean_clean,
        "product": {"name": product_name, "ean": ean_clean, "brand": None, "categories": None},
        "base_description": "",
        "verified": {},
        "images_used": 0,
    }

    paths: list[Path] = []
    # 1) Pobierz z URL-i
    if image_urls:
        from src.image_downloader import download_sources_to_dir
        urls_dir = work_dir / "urls"
        urls_dir.mkdir(parents=True, exist_ok=True)
        paths = download_sources_to_dir(image_urls, urls_dir)
    # 2) Zapisz wgrane (base64) do plików
    if uploaded_images_base64:
        upload_dir = work_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        for i, b64 in enumerate(uploaded_images_base64):
            raw = b64.split(",", 1)[-1].strip() if isinstance(b64, str) else b64
            try:
                data = base64.b64decode(raw)
            except Exception:
                continue
            ext = ".jpg"
            path = upload_dir / f"upload_{i:02d}_{_uuid.uuid4().hex[:8]}{ext}"
            path.write_bytes(data)
            paths.append(path)

    if not paths:
        result["error"] = "No images to analyze (URLs failed or no uploads)"
        return result
    result["images_used"] = len(paths)

    # 3) Analiza opisu (bez matching/quality – użytkownik zweryfikował)
    base_desc = analyze_images_for_description(paths)
    result["base_description"] = base_desc
    verified = verify_description_and_extract_data(
        paths, product_name, base_desc, lang=config.OUTPUT_LANG
    )
    result["verified"] = verified
    return result


def _save_result(result: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    desc = result.get("verified", {}).get("description_verified") or result.get("base_description", "")
    if desc:
        (out_dir / "description.txt").write_text(desc, encoding="utf-8")
    logger.info("Saved to %s", path)
