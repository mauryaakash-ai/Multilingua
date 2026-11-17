import argparse
import json
import sys

from .config import diagnose
from .pipeline import Pipeline


def run_cli():
    p = argparse.ArgumentParser(description="English-to-Hindi video dubbing research pipeline")
    p.add_argument("--config", default="configs/local.json")
    sub = p.add_subparsers(dest="action", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--audio-only", action="store_true")
    prep = sub.add_parser("prepare")
    prep.add_argument("video")
    prep.add_argument("--runs", default="runs")
    render = sub.add_parser("render")
    render.add_argument("job")
    render.add_argument("--review")
    render.add_argument("--audio-only", action="store_true", help="Explicitly skip lip editing")
    replay = sub.add_parser("replay")
    replay.add_argument("video")
    replay.add_argument("--runs", default="runs")
    replay.add_argument("--chunk-seconds", type=float, default=6)
    replay.add_argument("--max-waiting", type=int, default=2)
    replay.add_argument("--audio-only", action="store_true")
    ui = sub.add_parser("ui")
    ui.add_argument("--runs", default="runs")
    ui.add_argument("--port", type=int, default=7860)
    args = p.parse_args()
    if args.action == "doctor":
        checks = diagnose(args.config, args.audio_only)
        print(json.dumps(checks, indent=2))
        return 0 if checks["ready"] else 1
    if args.action == "ui":
        from .ui import launch

        launch(args.config, args.runs, args.port)
        return
    if args.action == "replay":
        from .replay import replay

        print(
            replay(
                args.config,
                args.video,
                args.runs,
                args.chunk_seconds,
                args.max_waiting,
                args.audio_only,
            )
        )
        return
    pipe = Pipeline(args.config)
    if args.action == "prepare":
        print(pipe.prepare(args.video, args.runs))
    elif args.action == "render":
        print(pipe.render(args.job, args.review, args.audio_only))


def main():
    try:
        return run_cli()
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Inspect the job status and logs before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
