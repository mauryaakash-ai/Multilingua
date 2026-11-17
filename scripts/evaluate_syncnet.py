"""Run official SyncNet face tracking and score every resulting track."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

p = argparse.ArgumentParser()
p.add_argument("videos", nargs="+")
p.add_argument("--output", required=True)
p.add_argument("--min-track", type=int, default=100)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
repo = root / "vendor/syncnet_python"
out = Path(a.output).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo))
import numpy as np
import torch
from SyncNetInstance import SyncNetInstance

model = repo / "data/syncnet_v2.model"
engine = SyncNetInstance()
engine.loadParameters(str(model))
results = []
for i, video in enumerate(a.videos):
    video = Path(video).resolve()
    reference = f"clip_{i:03d}"
    row = {
        "video": str(video),
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "reference": reference,
        "tracks": [],
    }
    try:
        with (out / f"{reference}.log").open("w") as log:
            subprocess.run(
                [
                    sys.executable,
                    "run_pipeline.py",
                    "--videofile",
                    str(video),
                    "--reference",
                    reference,
                    "--data_dir",
                    str(out),
                    "--min_track",
                    str(a.min_track),
                ],
                cwd=repo,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        tracks = sorted((out / "pycrop" / reference).glob("0*.avi"))
        if not tracks:
            raise ValueError("No face tracks; no valid synchronization score")
        for track in tracks:
            opt = SimpleNamespace(
                tmp_dir=str(out / "pytmp"), reference=reference, batch_size=20, vshift=15
            )
            with torch.inference_mode():
                offset, confidence, dist = engine.evaluate(opt, str(track))
            curve = np.mean(dist, axis=0)
            row["tracks"].append(
                {
                    "track": track.name,
                    "offset_frames": int(offset),
                    "offset_seconds": float(offset) / 25,
                    "min_distance": float(np.min(curve)),
                    "confidence": float(confidence),
                    "zero_offset_distance": float(curve[15]),
                    "evaluated_windows": len(dist),
                }
            )
        row["status"] = "measured"
    except Exception as e:
        row.update(status="failed", error=str(e))
    results.append(row)
    report = {
        "implementation": "https://github.com/joonson/syncnet_python",
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "checkpoint_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "fps": 25,
        "min_track_frames": a.min_track,
        "search_shift_frames": 15,
        "note": "Track-level SyncNet scores; Hindi calibration and human perceptual ratings are pending. Minimum distance searches offsets; inspect zero-offset distance and estimated offset too.",
        "results": results,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(row), flush=True)
if any(r["status"] == "failed" for r in results):
    sys.exit(1)
