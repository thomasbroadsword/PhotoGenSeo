"""
POST /api/run_from_images
Body: {
  "ean": "...",
  "productName": "...",
  "imageUrls": ["url1", "url2", ...],
  "uploadedImages": ["data:image/jpeg;base64,...", ...]  // opcjonalne
}
Używa tylko wybranych/wgranych zdjęć (bez search, bez matching). Zwraca wynik jak pipeline.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
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
        if not body:
            send_error(self, 400, "Brak body JSON")
            return
        ean = (body.get("ean") or "").strip()
        product_name = (body.get("productName") or body.get("product_name") or "").strip()
        image_urls = list(body.get("imageUrls") or body.get("image_urls") or [])
        uploaded = list(body.get("uploadedImages") or body.get("uploaded_images") or [])
        if not product_name:
            send_error(self, 400, "Wymagane: productName")
            return
        if not image_urls and not uploaded:
            send_error(self, 400, "Podaj imageUrls lub uploadedImages")
            return
        try:
            from src.pipeline import run_pipeline_from_selected_images
        except Exception as e:
            send_error(self, 500, f"Import: {e!s}")
            return
        with tempfile.TemporaryDirectory(prefix="photogen_") as tmp:
            work_dir = Path(tmp)
            try:
                result = run_pipeline_from_selected_images(
                    ean or "0",
                    product_name,
                    image_urls=image_urls,
                    uploaded_images_base64=uploaded,
                    work_dir=work_dir,
                    save_to_db=False,
                )
                send_json(self, 200, result)
            except Exception as e:
                send_error(self, 500, str(e))
