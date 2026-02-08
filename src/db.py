"""
Baza danych na Vercel (Postgres / Neon).

Tabele:
- pipeline_runs: każdy uruchomiony pipeline (EAN, szacunek kosztów, wynik JSON, created_at).
- product_images: pomniejszone zdjęcia tylko tych wykorzystanych (run_id, ean, image_data, content_type, wymiary, source_url, position).
"""
from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import config

logger = logging.getLogger(__name__)


def _get_conn():
    if not config.POSTGRES_URL:
        raise ValueError("POSTGRES_URL (lub DATABASE_URL) nie jest ustawiony")
    import psycopg
    return psycopg.connect(config.POSTGRES_URL)


@contextmanager
def get_connection() -> Generator[Any, None, None]:
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_tables() -> None:
    """Tworzy tabele jeśli nie istnieją (idempotentne)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    ean VARCHAR(32) NOT NULL,
                    product_name VARCHAR(512),
                    cost_estimate_usd NUMERIC(10,4),
                    cost_estimate_json JSONB,
                    result_json JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS product_images (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
                    ean VARCHAR(32) NOT NULL,
                    image_data BYTEA NOT NULL,
                    content_type VARCHAR(64) NOT NULL DEFAULT 'image/jpeg',
                    width INT,
                    height INT,
                    source_url VARCHAR(2048),
                    position INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_ean ON pipeline_runs(ean);
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON pipeline_runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_product_images_run_id ON product_images(run_id);
                CREATE INDEX IF NOT EXISTS idx_product_images_ean ON product_images(ean);
            """)
    logger.info("DB tables initialized")


def save_run(
    ean: str,
    product_name: str | None = None,
    cost_estimate: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> str:
    """
    Zapisuje nowy run (run_id=None) lub aktualizuje istniejący (run_id podany).
    Zwraca run_id (UUID). Przy nowym runie: zapisuje cost_estimate; przy update: result.
    """
    cost_usd = None
    cost_json = None
    if cost_estimate:
        cost_usd = cost_estimate.get("estimated_usd")
        cost_json = json.dumps(cost_estimate) if cost_estimate else None
    result_json = json.dumps(result, ensure_ascii=False) if result else None

    with get_connection() as conn:
        with conn.cursor() as cur:
            if run_id:
                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET product_name = COALESCE(%s, product_name),
                        cost_estimate_usd = COALESCE(%s, cost_estimate_usd),
                        cost_estimate_json = COALESCE(%s::jsonb, cost_estimate_json),
                        result_json = COALESCE(%s::jsonb, result_json)
                    WHERE id = %s;
                    """,
                    (product_name, cost_usd, cost_json, result_json, run_id),
                )
                return run_id
            rid = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO pipeline_runs (id, ean, product_name, cost_estimate_usd, cost_estimate_json, result_json)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb);
                """,
                (rid, ean, product_name, cost_usd, cost_json, result_json),
            )
            return rid


def save_used_images(
    run_id: str,
    ean: str,
    image_paths: list[Path],
    source_urls: list[str | None] | None = None,
) -> int:
    """
    Pomniejsza i zapisuje do product_images tylko przekazane zdjęcia (wykorzystane w pipeline).
    image_paths: lista ścieżek do plików (po matching + quality filter).
    source_urls: opcjonalna lista URL-i w tej samej kolejności.
    Zwraca liczbę zapisanych zdjęć.
    """
    from src.image_store import resize_image_for_storage

    source_urls = source_urls or []
    saved = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for i, path in enumerate(image_paths):
                try:
                    data, content_type, width, height = resize_image_for_storage(path)
                    url = source_urls[i] if i < len(source_urls) else None
                    cur.execute(
                        """
                        INSERT INTO product_images (run_id, ean, image_data, content_type, width, height, source_url, position)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (run_id, ean, data, content_type, width, height, url, i),
                    )
                    saved += 1
                except Exception as e:
                    logger.warning("Skip saving image %s: %s", path, e)
    return saved
