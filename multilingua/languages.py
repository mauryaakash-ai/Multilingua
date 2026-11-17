"""Explicit model-supported target languages; no silent language fallback."""

import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).with_name("languages.json")).read_text())


def language(code):
    if code not in CATALOG:
        raise ValueError(f"Unsupported target language: {code}")
    return CATALOG[code]


def validate_model_route(config):
    """Reject mixing Spanish adapters with Indic-language configurations."""
    target = config.get("target_language", "hi")
    language(target)
    expected = {"translate": "translate_nllb.py", "tts": "tts_xtts.py"}
    for stage, name in expected.items():
        command = config.get("commands", {}).get(stage, [])
        selected = len(command) > 1 and Path(command[1]).name == name
        if target == "es" and not selected:
            raise ValueError("Spanish requires configs/spanish.example.json and local NLLB/XTTS models")
        if target != "es" and selected:
            raise ValueError("Spanish model adapters cannot process an Indic target language")
