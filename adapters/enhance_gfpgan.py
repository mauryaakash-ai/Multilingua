"""Optional recorded-video enhancement; aligned face restoration, mouth-only pasteback."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--response", required=True)
    args = p.parse_args()
    r = json.loads(Path(args.request).read_text())
    root = Path(__file__).resolve().parents[1]
    for name in [
        "GFPGANv1.4.pth",
        "gfpgan/weights/detection_Resnet50_Final.pth",
        "gfpgan/weights/parsing_parsenet.pth",
    ]:
        if not (root / "models/restoration" / name).is_file():
            raise ValueError("GFPGAN quality mode is not installed locally: " + name)
    output = Path(r["output"]).resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/benchmark_mouth_restoration.py"),
            "--input",
            str(Path(r["video"]).resolve()),
            "--output",
            str(output),
            "--efficient",
            "--strength",
            str(r.get("strength", 0.65)),
        ],
        capture_output=True,
        text=True,
        timeout=r.get("timeout", 1800),
    )
    print(result.stdout, flush=True)
    print(result.stderr, file=sys.stderr, flush=True)
    if result.returncode or "Failed inference for GFPGAN:" in result.stdout:
        raise RuntimeError("GFPGAN enhancement failed; inspect the enhancement log")
    report = json.loads(output.with_suffix(".json").read_text())
    report.pop("frames_timing", None)
    Path(args.response).write_text(json.dumps({"video": str(output), "report": report}, indent=2))


if __name__ == "__main__":
    main()
