"""Create a portable human-review bundle without inventing reviewer approval."""

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jobs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, job in enumerate(args.jobs):
        output = job / "output.mp4"
        if not output.is_file():
            raise ValueError(f"No completed output: {output}")
        name = f"clip_{index:03d}"
        folder = args.output / name
        folder.mkdir()
        for filename in (
            "source.mp4",
            "input.mp4",
            "output.mp4",
            "segments.json",
            "reviewed_segments.json",
            "subtitles.srt",
            "provenance.json",
            "alignment.json",
            "video.mp4",
            "translate_request.json",
            "translate_response.json",
            "tts_request.json",
        ):
            path = job / filename
            if path.is_file():
                shutil.copyfile(path, folder / filename)
        state_path = job / "job.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if not state and (job / "tts_request.json").exists():
            state = {
                "target_language": json.loads((job / "tts_request.json").read_text()).get(
                    "language", "unknown"
                )
            }
        rows.append(
            {
                "clip": name,
                "language": state.get("target_language", "unknown"),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "reviewer": "",
                "fluent_language": "",
                "translation_1_to_5": "",
                "voice_1_to_5": "",
                "lip_sync_1_to_5": "",
                "mouth_detail_1_to_5": "",
                "critical_error": "",
                "notes": "",
                "approved": "pending",
            }
        )
    with (args.output / "reviews.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "README.txt").write_text(
        "Native-speaker review: PENDING\nListen and watch each complete original and dubbed clip. Read the reviewed translations. Rate each dimension from 1 (poor) to 5 (excellent), document mistranslations, missing words, pronunciation errors, lip lag and blur. Supply reviewer name and fluent language. Mark approved only after actual review. File hashes bind ratings to these exact outputs. Automated metrics are not human approval.\n"
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
