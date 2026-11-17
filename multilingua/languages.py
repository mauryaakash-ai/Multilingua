"""Explicit model-supported target languages; no silent language fallback."""

import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).with_name("languages.json")).read_text())


def language(code):
    if code not in CATALOG:
        raise ValueError(f"Unsupported target language: {code}")
    return CATALOG[code]
