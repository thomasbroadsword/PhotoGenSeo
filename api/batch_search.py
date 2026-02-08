"""
POST /api/batch_search
Body: { "eans": ["590...", ...] }  (max 10)
Zwraca: { "products": { "ean": { "product": { name, ean, brand }, "sources": [ { image_url, page_url, title } ] } } }
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._shared import parse_json_body, send_error, send_json

MAX_EANS = 10


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        body = parse_json_body(self)
        if not body or "eans" not in body:
            send_error(self, 400, "Brak pola 'eans' w body")
            return
        eans = [str(e).strip() for e in body["eans"] if str(e).strip()][:MAX_EANS]
        if not eans:
            send_error(self, 400, "Lista EAN jest pusta")
            return
        try:
            import config
            from src.ean_lookup import lookup_product
            from src.source_search import search_image_sources
        except Exception as e:
            send_error(self, 500, f"Import: {e!s}")
            return
        products = {}
        for ean in eans:
            ean_clean = "".join(c for c in ean if c.isdigit())
            if not ean_clean:
                products[ean] = {"error": "Invalid EAN"}
                continue
            try:
                product = lookup_product(ean_clean)
                sources, _ = search_image_sources(
                    product.name,
                    ean=product.ean,
                    min_count=config.MIN_IMAGES_TO_FETCH,
                )
                products[ean_clean] = {
                    "product": {
                        "name": product.name,
                        "ean": product.ean,
                        "brand": product.brand,
                        "categories": product.categories,
                    },
                    "sources": [
                        {
                            "image_url": s.image_url,
                            "page_url": s.page_url,
                            "title": s.title,
                            "source_domain": s.source_domain,
                        }
                        for s in sources
                    ],
                }
            except Exception as e:
                products[ean_clean] = {"error": str(e)}
        send_json(self, 200, {"products": products})
