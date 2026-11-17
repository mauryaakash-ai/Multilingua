import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for _ in range(1200):
    if (root / "runs/evaluation/latentsync-grid/steps-15-guidance-1.json").exists():
        break
    time.sleep(1)
else:
    raise TimeoutError("Quality sweep not finished")
with (root / "runs/profiling/tts-fp16.log").open("w") as log:
    subprocess.run(
        [
            str(root / ".venv-voice/bin/python"),
            str(root / "benchmarks/profile_stage.py"),
            "--stage",
            "tts",
            "--tts-dtype",
            "float16",
            "--fixture",
            str(root / "runs/profiling/baseline/fixture.json"),
            "--output",
            str(root / "runs/profiling/tts-fp16.json"),
        ],
        cwd=root,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
