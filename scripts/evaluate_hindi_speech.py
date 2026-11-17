"""ASR consistency proxy for generated Hindi speech, not a human MOS score."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faster_whisper import WhisperModel

from multilingua.evaluation import error_rates

p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--audio", required=True)
p.add_argument("--segments", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
m = WhisperModel(a.model, device="cpu", compute_type="int8")
start = time.monotonic()
segments, info = m.transcribe(a.audio, language="hi", vad_filter=True, beam_size=5)
hyp = " ".join(s.text.strip() for s in segments)
ref = " ".join(s["translation"] for s in json.loads(Path(a.segments).read_text()))
r = {
    "reference": ref,
    "hypothesis": hyp,
    "metrics": error_rates(ref, hyp),
    "asr_model": a.model,
    "inference_seconds": time.monotonic() - start,
    "interpretation": "ASR consistency proxy only. Errors combine recognizer limitations, timing changes, and synthesis errors. Not a human intelligibility score.",
}
Path(a.output).write_text(json.dumps(r, ensure_ascii=False, indent=2))
print(json.dumps(r, ensure_ascii=False))
