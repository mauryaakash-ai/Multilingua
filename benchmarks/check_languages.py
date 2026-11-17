"""Generate inspectable Hindi text, audio and lip-sync samples."""

import json
import math
import time
from pathlib import Path

from multilingua import media
from multilingua.languages import language
from multilingua.pipeline import Pipeline, write_json
from multilingua.resident import ResidentPool

root = Path(__file__).resolve().parents[1]
out = root / "runs/evaluation/languages"
out.mkdir(parents=True, exist_ok=True)
pool = ResidentPool(out / "worker-logs")
rows = []
try:
    for code in ["hi"]:
        work = out / code
        work.mkdir(exist_ok=True)
        p = Pipeline(root / "configs/local.json", resident_pool=pool)
        entry = language(code)
        start = time.perf_counter()
        mt, mt_time = p.adapter(
            "translate",
            work,
            {
                "texts": ["Thank you for joining us today."],
                "source": "eng_Latn",
                "target": entry["translation_target"],
            },
        )
        text = mt["texts"][0]
        tts, tts_time = p.adapter(
            "tts",
            work,
            {
                **p.config["tts"],
                "language": code,
                "description": entry["description"],
                "text": text,
                "output": str(work / "raw.wav"),
            },
        )
        seconds = math.ceil(media.duration(work / "raw.wav") * 25) / 25
        media.fit_audio(work / "raw.wav", work / "audio.wav", seconds)
        media.cut(root / "runs/hdtf-first/source.mp4", work / "video.mp4", 0, seconds)
        result, lip_time = p.adapter(
            "lipsync",
            work,
            {
                "video": str(work / "video.mp4"),
                "audio": str(work / "audio.wav"),
                "output": str(work / "output.mp4"),
                **p.config["lipsync"],
            },
        )
        row = {
            "language": code,
            "translation": text,
            "voice": entry["voice"],
            "audio_seconds": seconds,
            "translation_seconds": mt_time,
            "tts_seconds": tts_time,
            "lipsync_seconds": lip_time,
            "total_seconds": time.perf_counter() - start,
            "native_review": "pending",
            "chrF++": None,
            "reference_translation": None,
        }
        rows.append(row)
        write_json(out / "report.json", {"results": rows})
        print(json.dumps(row, ensure_ascii=False), flush=True)
finally:
    pool.close()
