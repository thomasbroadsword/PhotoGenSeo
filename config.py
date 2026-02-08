"""Konfiguracja – klucze API i progi pipeline."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ścieżki
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
OUTPUT_DIR = DATA_DIR / "output"

# API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
EAN_DB_JWT = os.getenv("EAN_DB_JWT", "").strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()

# Parametry pipeline
MIN_IMAGES_TO_FETCH = 10
MAX_IMAGES_TO_ANALYZE = 15
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# AI matching produktów – minimalna pewność, że to ten sam produkt (0–1)
PRODUCT_MATCH_MIN_CONFIDENCE = 0.75

# Odrzucanie: min. score unikalności zdjęcia (0–1), poniżej = odrzuć
IMAGE_UNIQUENESS_MIN_SCORE = 0.4

# Źródła: odrzucaj strony o wiarygodności poniżej (0–1)
SOURCE_TRUST_MIN_SCORE = 0.3

# Język wyników (opis, weryfikacja)
OUTPUT_LANG = "pl"

# Cennik Claude (szacowanie kosztów) – USD za 1M tokenów (Sonnet 4: input $3, output $15)
CLAUDE_PRICE_INPUT_PER_MTOK = float(os.getenv("CLAUDE_PRICE_INPUT_PER_MTOK", "3.0"))
CLAUDE_PRICE_OUTPUT_PER_MTOK = float(os.getenv("CLAUDE_PRICE_OUTPUT_PER_MTOK", "15.0"))

# Baza danych (Vercel Postgres / Neon – POSTGRES_URL lub DATABASE_URL)
POSTGRES_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", "")).strip()

# Zapis zdjęć do bazy: tylko wykorzystane (po matching + quality), po pomniejszeniu
IMAGE_STORE_MAX_PX = int(os.getenv("IMAGE_STORE_MAX_PX", "800"))  # max bok w px
IMAGE_STORE_QUALITY = int(os.getenv("IMAGE_STORE_QUALITY", "85"))  # JPEG quality 1–100
