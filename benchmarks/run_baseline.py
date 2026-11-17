import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from multilingua.config import load_config

out = root / "runs/profiling/baseline"
config = load_config(root / "configs/local.json")
workers = {
    "asr": config["commands"]["asr"][0],
    "translation": config["commands"]["translate"][0],
    "tts": config["commands"]["tts"][0],
    "musetalk": config["lipsync"]["python"],
    "ffmpeg": Path(sys.executable),
}
for stage, python in workers.items():
    with (out / f"{stage}.log").open("w") as log:
        result = subprocess.run(
            [
                str(python),
                str(root / "benchmarks/profile_stage.py"),
                "--stage",
                stage,
                "--fixture",
                str(out / "fixture.json"),
                "--output",
                str(out / f"{stage}.json"),
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    print(stage, result.returncode, flush=True)
    if result.returncode:
        sys.exit(result.returncode)
