"""
POST /api/search_more
Body: { "ean": "...", "productName": "..." }
Zwraca: { "sources": [ { image_url, page_url, title } ] }  – kolejna porcja zdjęć
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._shared import parse_json_body, send_error, send_json


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        body = parse_json_body(self)
        if not body or not body.get("productName"):
            send_error(self, 400, "Wymagane: productName")
            return
        ean = (body.get("ean") or "").strip()
        product_name = (body.get("productName") or "").strip()
        if not product_name:
            send_error(self, 400, "productName nie może być puste")
            return
        try:
            import config
            from src.source_search import search_image_sources
        except Exception as e:
            send_error(self, 500, f"Import: {e!s}")
            return
        try:
            sources, _ = search_image_sources(
                product_name,
                ean=ean or None,
                min_count=config.MIN_IMAGES_TO_FETCH,
            )
            send_json(self, 200, {
                "sources": [
                    {
                        "image_url": s.image_url,
                        "page_url": s.page_url,
                        "title": s.title,
                        "source_domain": s.source_domain,
                    }
                    for s in sources
                ],
            })
        except Exception as e:
            send_error(self, 500, str(e))
