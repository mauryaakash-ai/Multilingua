"""Explicit model-supported target languages; English to Hindi only."""

import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).with_name("languages.json")).read_text())


def language(code):
    if code not in CATALOG:
        raise ValueError(
            f"Unsupported target language: {code}. Only English to Hindi ('hi') is supported."
        )
    return CATALOG[code]


def validate_model_route(config):
    """Enforce English to Hindi dubbing only."""
    target = config.get("target_language", "hi")
    if target != "hi":
        raise ValueError(f"Only English to Hindi dubbing is supported, got: {target}")
    return language(target)
