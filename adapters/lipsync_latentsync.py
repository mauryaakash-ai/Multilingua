"""Pipeline adapter for the locally validated LatentSync preview configuration."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from multilingua import media


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--response", required=True)
    a = p.parse_args()
    r = json.loads(Path(a.request).read_text())
    source = media.probe(r["video"])
    video = next(s for s in source["streams"] if s["codec_type"] == "video")
    seconds = float(video["duration"])
    with tempfile.TemporaryDirectory(prefix="latent_adapter_") as tmp:
        output = Path(tmp) / "render.mp4"
        subprocess.run(
            [
                sys.executable,
                str(root / "adapters/latentsync_experiment.py"),
                "--video",
                r["video"],
                "--audio",
                r["audio"],
                "--output",
                str(output),
                "--steps",
                "20",
                "--frames",
                "8",
            ],
            check=True,
            timeout=7200,
        )
        result = next(s for s in media.probe(output)["streams"] if s["codec_type"] == "video")
        if int(result["nb_frames"]) < int(video["nb_frames"]):
            raise RuntimeError("LatentSync returned too few video frames")
        # Drop only surplus generated frames; retain the original fitted audio.
        media.ffmpeg(
            "-i",
            output,
            "-i",
            r["audio"],
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            r["output"],
        )
        final = next(s for s in media.probe(r["output"])["streams"] if s["codec_type"] == "video")
        if int(final["nb_frames"]) != int(video["nb_frames"]):
            raise RuntimeError("LatentSync frame count mismatch")
    Path(a.response).write_text(
        json.dumps(
            {"video": r["output"], "backend": "latentsync", "steps": 20, "frames_per_batch": 8}
        )
    )


if __name__ == "__main__":
    main()
