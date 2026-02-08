"""Wspólne dla API: ścieżka projektu, parsowanie body, odpowiedź JSON."""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from typing import Any

# Root projektu (nad api/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Załaduj .env (Vercel i tak nadpisuje zmiennymi środowiskowymi)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        return None
    raw = handler.rfile.read(content_length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def send_json(handler: BaseHTTPRequestHandler, status: int, data: Any) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def send_error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    send_json(handler, status, {"error": message})
