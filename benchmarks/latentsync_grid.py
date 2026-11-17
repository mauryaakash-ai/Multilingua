"""Controlled short-clip quality/speed trials; does not change the app preset."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / "runs/evaluation/latentsync-grid"
out.mkdir(parents=True, exist_ok=True)
for steps in [10, 12, 15]:
    output = out / f"steps-{steps}-guidance-1.mp4"
    subprocess.run(
        [
            sys.executable,
            str(root / "adapters/latentsync_experiment.py"),
            "--video",
            str(root / "runs/lip-quality/preview-source.mp4"),
            "--audio",
            str(root / "runs/lip-quality/preview-audio.wav"),
            "--output",
            str(output),
            "--steps",
            str(steps),
            "--guidance",
            "1",
        ],
        check=True,
    )
    print(output.with_suffix(".json").read_text(), flush=True)
