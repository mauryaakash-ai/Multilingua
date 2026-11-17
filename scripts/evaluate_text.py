"""Input JSONL requires independent references; missing references stay unscored."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from multilingua.evaluation import error_rates

p = argparse.ArgumentParser()
p.add_argument("manifest")
p.add_argument("--output", required=True)
a = p.parse_args()
rows = []
for line in Path(a.manifest).read_text().splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    out = {"id": r["id"], "speaker_id": r["speaker_id"]}
    for task in ("asr", "tts"):
        ref = r.get(task + "_reference")
        hyp = r.get(task + "_hypothesis")
        out[task] = (
            error_rates(ref, hyp)
            if ref and hyp is not None
            else {"status": "unscored", "reason": "Missing independent reference or hypothesis"}
        )
    if r.get("translation_reference") and r.get("translation_hypothesis"):
        from sacrebleu.metrics import CHRF

        metric = CHRF(word_order=2)
        score = metric.corpus_score([r["translation_hypothesis"]], [[r["translation_reference"]]])
        out["translation"] = {
            "chrf_plus_plus": score.score,
            "signature": str(metric.get_signature()),
        }
    else:
        out["translation"] = {
            "status": "unscored",
            "reason": "Missing independent translation reference",
        }
    out["human_ratings"] = r.get("human_ratings", {"status": "unscored"})
    rows.append(out)
Path(a.output).write_text(
    json.dumps(
        {
            "items": rows,
            "note": "Do not substitute model outputs for independent references. Small development samples do not establish population quality.",
        },
        ensure_ascii=False,
        indent=2,
    )
)
