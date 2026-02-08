"""
Wspólny klient Anthropic (Claude) do wizji i tekstu.
Pomocnicze: ładowanie obrazów do base64, budowa wiadomości z załącznikami.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

import anthropic
import config

logger = logging.getLogger(__name__)


def load_image_as_base64(path: Path) -> tuple[str, str] | None:
    """Zwraca (media_type, base64_string) lub None."""
    path = Path(path)
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    media_type = "image/jpeg"
    if suffix == ".png":
        media_type = "image/png"
    elif suffix == ".webp":
        media_type = "image/webp"
    elif suffix == ".gif":
        media_type = "image/gif"
    try:
        data = path.read_bytes()
        return media_type, base64.standard_b64encode(data).decode("ascii")
    except Exception as e:
        logger.debug("Cannot read image %s: %s", path, e)
        return None


def build_image_content_block(path: Path) -> dict[str, Any] | None:
    """Blok content dla API: source type image."""
    out = load_image_as_base64(path)
    if not out:
        return None
    media_type, data = out
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def get_client() -> anthropic.Anthropic:
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def message_with_images(
    system: str,
    user_text: str,
    image_paths: list[Path],
    max_tokens: int = 4096,
) -> str:
    """
    Wysyła do Claude wiadomość z tekstem i załączonymi obrazami.
    Zwraca treść odpowiedzi (text).
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for p in image_paths:
        block = build_image_content_block(p)
        if block:
            content.append(block)
    client = get_client()
    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return msg.content[0].text if msg.content else ""
