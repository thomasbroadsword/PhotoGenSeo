#!/usr/bin/env python3
"""
PhotoGenSeo – pipeline: EAN → zdjęcia (SerpAPI/DuckDuckGo) → AI matching → weryfikacja opisu (EAN, wymiary).

Użycie:
  python main.py <EAN>
  python main.py 5901234123457
"""
import argparse
import logging
import sys
from pathlib import Path

# dodaj root projektu do ścieżki
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from src.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PhotoGenSeo: EAN → zdjęcia → opis SEO (SerpAPI, Claude, weryfikacja)"
    )
    parser.add_argument("ean", help="Kod EAN produktu")
    parser.add_argument(
        "--min-images",
        type=int,
        default=config.MIN_IMAGES_TO_FETCH,
        help="Min. liczba zdjęć do wyszukania (domyślnie %s)" % config.MIN_IMAGES_TO_FETCH,
    )
    parser.add_argument(
        "--output-subdir",
        default=None,
        help="Podkatalog w data/output/ (domyślnie EAN)",
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Tylko analiza kosztów: pobierz zdjęcia, oszacuj koszt, zapisz (opcjonalnie do bazy). Bez wywołań Claude.",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Nie zapisuj do bazy (Vercel Postgres).",
    )
    args = parser.parse_args()

    if not args.estimate_only and not config.ANTHROPIC_API_KEY:
        logger.error("Ustaw ANTHROPIC_API_KEY w .env (nie potrzebny przy --estimate-only)")
        sys.exit(1)

    result = run_pipeline(
        args.ean,
        min_images=args.min_images,
        output_subdir=args.output_subdir,
        estimate_only=args.estimate_only,
        save_to_db=not args.no_db,
    )
    if result.get("error"):
        logger.error("Pipeline error: %s", result["error"])
        sys.exit(2)
    logger.info("Done. Output: %s", result.get("output_dir"))
    print("Wynik zapisany w:", result.get("output_dir"))
    cost = result.get("cost_estimate", {})
    if cost:
        print("Szacowany koszt (przed generacją): ~%.4f USD" % cost.get("estimated_usd", 0))
    if args.estimate_only:
        print("Uruchom bez --estimate-only, aby wygenerować opis i zapisać zdjęcia do bazy.")
        return
    v = result.get("verified", {})
    if v:
        print("EAN z zdjęć:", v.get("ean_from_images"))
        print("Wymiary z zdjęć:", v.get("dimensions_from_images"))
    if result.get("images_saved_to_db") is not None:
        print("Zdjęć zapisanych do bazy (pomniejszone):", result["images_saved_to_db"])


if __name__ == "__main__":
    main()
