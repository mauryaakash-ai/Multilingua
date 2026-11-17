"""Portable, trusted local configuration and dependency diagnostics."""

import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ("asr", "translate", "tts", "lipsync")


def load_config(path):
    path = Path(path).resolve()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            f"Configuration not found: {path}. Copy configs/local.example.json "
            "to configs/local.json and set your model paths."
        ) from exc
    if not isinstance(value, dict) or not isinstance(value.get("commands"), dict):
        raise ValueError("Configuration must be an object containing a commands object")

    def expand(item):
        if isinstance(item, str):
            return os.path.expanduser(
                os.path.expandvars(
                    item.replace("{project}", str(ROOT)).replace("{python}", sys.executable)
                )
            )
        if isinstance(item, list):
            return [expand(x) for x in item]
        if isinstance(item, dict):
            return {key: expand(x) for key, x in item.items()}
        return item

    value = expand(value)
    for name, default, low, high in (
        ("timeout_seconds", 1800, 1, 7200),
        ("max_speech_speed", 1.25, 1, 1.25),
    ):
        number = value.get(name, default)
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
            or not low <= number <= high
        ):
            raise ValueError(f"{name} must be a finite number between {low} and {high}")
    for stage in ("tts", "lipsync"):
        if not isinstance(value.get(stage, {}), dict):
            raise ValueError(f"{stage} settings must be an object")
    return value


def command(config, stage):
    args = config["commands"].get(stage)
    if not isinstance(args, list) or not args or not all(isinstance(x, str) and x for x in args):
        raise ValueError(f"Missing command array for {stage} in configuration")
    return args


def diagnose(path, audio_only=False):
    """No downloads or model inference; successful path checks do not certify models."""
    checks = []

    def add(name, ok, detail, required=True):
        checks.append(dict(name=name, ok=bool(ok), detail=detail, required=required))

    for binary in ("ffmpeg", "ffprobe"):
        found = shutil.which(binary)
        add(binary, found, found or "Install FFmpeg and add its bin directory to PATH.")
    add(
        "GPU tooling",
        shutil.which("nvidia-smi"),
        "Run nvidia-smi to verify driver access; this check does not benchmark VRAM.",
        False,
    )
    try:
        config = load_config(path)
    except (ValueError, OSError) as exc:
        add("configuration", False, str(exc))
    else:
        add("configuration", True, str(Path(path).resolve()))
        for stage in STAGES[:3] if audio_only else STAGES:
            try:
                args = command(config, stage)
                found = shutil.which(args[0])
                add(stage, found, found or f"Executable not found: {args[0]}")
                for arg in args[1:]:
                    if arg.endswith(".py"):
                        add(f"{stage} script", Path(arg).is_file(), arg)
            except ValueError as exc:
                add(stage, False, str(exc))
        tts = config.get("tts", {})
        if "reference_audio" in tts:
            add(
                "reference voice",
                Path(tts["reference_audio"]).is_file()
                and bool(tts.get("reference_text", "").strip()),
                "Use a permitted reference WAV and its exact transcript.",
            )
        if not audio_only:
            lip = config.get("lipsync", {})
            if "repo" in lip:
                for asset in (
                    "scripts/inference.py",
                    "models/musetalkV15/unet.pth",
                    "models/musetalkV15/musetalk.json",
                ):
                    asset_path = Path(lip["repo"]) / asset
                    add("MuseTalk asset", asset_path.is_file(), str(asset_path))
                add(
                    "MuseTalk Python",
                    shutil.which(lip.get("python", "")),
                    lip.get("python", "Set lipsync.python"),
                )
    return {
        "ready": all(c["ok"] for c in checks if c["required"]),
        "checks": checks,
        "note": "Local dependency checks only. Model imports, access, auxiliary weights, "
        "licenses and a real inference rehearsal must also pass.",
    }
