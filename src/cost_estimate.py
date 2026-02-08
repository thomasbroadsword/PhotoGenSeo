"""
Analiza kosztów przed generowaniem opisu (wywołania Claude API).

Szacuje koszt na podstawie liczby zdjęć: matching (batche), quality filter (batche),
analiza opisu (1 wywołanie), weryfikacja opisu (1 wywołanie).
Cennik: konfigurowalny w config (Sonnet 4: input $3/MTok, output $15/MTok).
Obrazy liczone jako ~1600 tokenów wejścia każdy (wg dokumentacji Anthropic).
"""
from __future__ import annotations

import math
from typing import Any

import config

# Szacunki tokenów (do aktualizacji przy zmianie promptów)
TOKENS_SYSTEM_MATCHING = 450
TOKENS_USER_MATCHING = 120
TOKENS_OUTPUT_MATCHING_PER_IMAGE = 80

TOKENS_SYSTEM_QUALITY = 500
TOKENS_USER_QUALITY = 150
TOKENS_OUTPUT_QUALITY_PER_IMAGE = 80

TOKENS_SYSTEM_ANALYZE = 350
TOKENS_USER_ANALYZE = 50
TOKENS_OUTPUT_ANALYZE = 1500

TOKENS_SYSTEM_VERIFY = 550
TOKENS_USER_VERIFY = 200
TOKENS_OUTPUT_VERIFY = 800

TOKENS_PER_IMAGE_INPUT = 1600  # orientacyjnie dla obrazu w API


def _batch_count(n: int, batch_size: int) -> int:
    return max(1, math.ceil(n / batch_size))


def estimate_generation_cost(num_images: int) -> dict[str, Any]:
    """
    Szacuje koszt (USD) generacji opisu dla danej liczby zdjęć (po pobraniu, przed matchingiem).

    Zakłada: wszystkie zdjęcia przejdą matching i quality (górna granica kosztu),
    potem analiza i weryfikacja na min(num_images, MAX_IMAGES_TO_ANALYZE).
    """
    batch_size = 10
    n = min(num_images, config.MAX_IMAGES_TO_ANALYZE * 2)  # cap dla realizmu
    n_analyze = min(n, config.MAX_IMAGES_TO_ANALYZE)

    # Matching: batche po 10 zdjęć
    batches_match = _batch_count(n, batch_size)
    input_match = batches_match * (
        TOKENS_SYSTEM_MATCHING + TOKENS_USER_MATCHING
        + batch_size * TOKENS_PER_IMAGE_INPUT
    )
    output_match = batches_match * batch_size * TOKENS_OUTPUT_MATCHING_PER_IMAGE

    # Quality: batche po 10
    batches_quality = _batch_count(n, batch_size)
    input_quality = batches_quality * (
        TOKENS_SYSTEM_QUALITY + TOKENS_USER_QUALITY
        + batch_size * TOKENS_PER_IMAGE_INPUT
    )
    output_quality = batches_quality * batch_size * TOKENS_OUTPUT_QUALITY_PER_IMAGE

    # Analiza opisu: 1 wywołanie, do n_analyze zdjęć
    input_analyze = (
        TOKENS_SYSTEM_ANALYZE + TOKENS_USER_ANALYZE
        + n_analyze * TOKENS_PER_IMAGE_INPUT
    )
    output_analyze = TOKENS_OUTPUT_ANALYZE

    # Weryfikacja: 1 wywołanie
    input_verify = (
        TOKENS_SYSTEM_VERIFY + TOKENS_USER_VERIFY
        + n_analyze * TOKENS_PER_IMAGE_INPUT
    )
    output_verify = TOKENS_OUTPUT_VERIFY

    total_input = input_match + input_quality + input_analyze + input_verify
    total_output = output_match + output_quality + output_analyze + output_verify

    input_per_mtok = total_input / 1_000_000
    output_per_mtok = total_output / 1_000_000
    cost_input = input_per_mtok * config.CLAUDE_PRICE_INPUT_PER_MTOK
    cost_output = output_per_mtok * config.CLAUDE_PRICE_OUTPUT_PER_MTOK
    total_usd = round(cost_input + cost_output, 4)

    return {
        "num_images_assumed": num_images,
        "num_images_capped": n,
        "num_images_for_analyze_verify": n_analyze,
        "breakdown": {
            "matching": {
                "batches": batches_match,
                "input_tokens": input_match,
                "output_tokens": output_match,
                "usd_input": round(input_match / 1_000_000 * config.CLAUDE_PRICE_INPUT_PER_MTOK, 4),
                "usd_output": round(output_match / 1_000_000 * config.CLAUDE_PRICE_OUTPUT_PER_MTOK, 4),
            },
            "quality_filter": {
                "batches": batches_quality,
                "input_tokens": input_quality,
                "output_tokens": output_quality,
                "usd_input": round(input_quality / 1_000_000 * config.CLAUDE_PRICE_INPUT_PER_MTOK, 4),
                "usd_output": round(output_quality / 1_000_000 * config.CLAUDE_PRICE_OUTPUT_PER_MTOK, 4),
            },
            "analyze_description": {
                "input_tokens": input_analyze,
                "output_tokens": output_analyze,
                "usd_input": round(input_analyze / 1_000_000 * config.CLAUDE_PRICE_INPUT_PER_MTOK, 4),
                "usd_output": round(output_analyze / 1_000_000 * config.CLAUDE_PRICE_OUTPUT_PER_MTOK, 4),
            },
            "verify_description": {
                "input_tokens": input_verify,
                "output_tokens": output_verify,
                "usd_input": round(input_verify / 1_000_000 * config.CLAUDE_PRICE_INPUT_PER_MTOK, 4),
                "usd_output": round(output_verify / 1_000_000 * config.CLAUDE_PRICE_OUTPUT_PER_MTOK, 4),
            },
        },
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_usd": total_usd,
        "currency": "USD",
    }
