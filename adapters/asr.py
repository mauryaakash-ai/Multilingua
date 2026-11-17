import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--request")
p.add_argument("--response")
p.add_argument("--model", default="small")
p.add_argument("--device", default="cpu")
a = p.parse_args()
r = json.loads(Path(a.request).read_text(encoding="utf-8"))
from faster_whisper import WhisperModel

m = WhisperModel(a.model, device=a.device, compute_type="float16" if a.device == "cuda" else "int8")
segments, info = m.transcribe(r["audio"], language=r["language"], vad_filter=True, beam_size=5)
# Whisper may place a final segment beyond EOF; bound timestamps to decoded audio.
out = [
    {"start": max(0.0, s.start), "end": min(info.duration, s.end), "text": s.text.strip()}
    for s in segments
    if s.text.strip() and min(info.duration, s.end) > max(0.0, s.start)
]
Path(a.response).write_text(json.dumps({"segments": out}, ensure_ascii=False), encoding="utf-8")
