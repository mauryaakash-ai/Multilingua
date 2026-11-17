import argparse
import json
from .pipeline import Pipeline
from .config import diagnose

def main():
    p = argparse.ArgumentParser(description='English-to-Hindi video dubbing research pipeline')
    p.add_argument('--config', default='configs/local.json')
    sub = p.add_subparsers(dest='action', required=True)
    doctor = sub.add_parser('doctor')
    doctor.add_argument('--audio-only', action='store_true')
    prep = sub.add_parser('prepare'); prep.add_argument('video'); prep.add_argument('--runs', default='runs')
    render = sub.add_parser('render'); render.add_argument('job'); render.add_argument('--review')
    render.add_argument('--audio-only', action='store_true', help='Explicitly skip lip editing')
    replay = sub.add_parser('replay')
    replay.add_argument('video'); replay.add_argument('--runs', default='runs')
    replay.add_argument('--chunk-seconds', type=float, default=6)
    replay.add_argument('--max-waiting', type=int, default=2)
    replay.add_argument('--audio-only', action='store_true')
    sub.add_parser('ui')
    args = p.parse_args()
    if args.action == 'doctor':
        checks = diagnose(args.config, args.audio_only)
        print(json.dumps(checks, indent=2))
        return 0 if checks['ready'] else 1
    if args.action == 'ui':
        from .ui import launch
        launch(args.config); return
    if args.action == 'replay':
        from .replay import replay
        print(replay(args.config,args.video,args.runs,args.chunk_seconds,args.max_waiting,args.audio_only))
        return
    pipe = Pipeline(args.config)
    if args.action == 'prepare': print(pipe.prepare(args.video,args.runs))
    elif args.action == 'render': print(pipe.render(args.job,args.review,args.audio_only))

if __name__ == '__main__':
    raise SystemExit(main())
