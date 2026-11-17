"""Private Unix-socket worker retaining model factories across adapter calls.
Serial within each stage worker; coordinated by ResidentPool.
"""

import argparse
import contextlib
import json
import os
import runpy
import socketserver
import subprocess
import sys
import traceback
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--socket", required=True)
p.add_argument("--stage", required=True)
p.add_argument("--adapter")
a = p.parse_args()
parent_pid = os.getppid()


def cached_factory(owner, name):
    original = getattr(owner, name)
    cache = {}

    def factory(*args, **kwargs):
        key = repr((args, sorted(kwargs.items())))
        if key not in cache:
            cache.clear()  # Bound each model factory to one active configuration.
            cache[key] = original(*args, **kwargs)
        return cache[key]

    setattr(owner, name, staticmethod(factory) if isinstance(owner, type) else factory)


if a.stage == "asr":
    import faster_whisper

    cached_factory(faster_whisper, "WhisperModel")
elif a.stage == "translate":
    if a.adapter == "translate_marian.py":
        from transformers import MarianMTModel, MarianTokenizer

        cached_factory(MarianTokenizer, "from_pretrained")
        cached_factory(MarianMTModel, "from_pretrained")
    else:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        cached_factory(AutoTokenizer, "from_pretrained")
        cached_factory(AutoModelForSeq2SeqLM, "from_pretrained")
elif a.stage == "tts":
    from transformers import AutoTokenizer

    cached_factory(AutoTokenizer, "from_pretrained")
    if a.adapter == "tts_mms.py":
        from transformers import VitsModel

        cached_factory(VitsModel, "from_pretrained")
    else:
        from parler_tts import ParlerTTSForConditionalGeneration

        cached_factory(ParlerTTSForConditionalGeneration, "from_pretrained")
elif a.stage == "lipsync":
    os.chdir(os.environ["MULTILINGUA_MUSETALK_REPO"])
    sys.path.insert(0, os.getcwd())
    import musetalk.utils.face_parsing as parsing
    import musetalk.utils.utils as muse_utils
    from transformers import WhisperModel

    cached_factory(muse_utils, "load_all_model")
    cached_factory(WhisperModel, "from_pretrained")
    original_model_init = parsing.FaceParsing.model_init
    parser_net = []

    def shared_parser(self, *args, **kwargs):
        if not parser_net:
            parser_net.append(original_model_init(self, *args, **kwargs))
        return parser_net[0]

    parsing.FaceParsing.model_init = shared_parser
    import torch

    torch.set_num_threads(4)
else:
    raise ValueError("Unsupported resident stage")
original_run = subprocess.run


def resident_run(command, *args, **kwargs):
    if (
        a.stage == "lipsync"
        and len(command) > 1
        and (
            command[1:3] == ["-m", "scripts.inference"]
            or str(command[1]).endswith("musetalk_quality_runner.py")
        )
    ):
        previous = sys.argv
        cwd = os.getcwd()
        try:
            os.chdir(kwargs["cwd"])
            sys.argv = ["scripts.inference", *command[3:]]
            if command[1:3] == ["-m", "scripts.inference"]:
                runpy.run_module("scripts.inference", run_name="__main__")
            else:
                import musetalk.utils.blending as blending

                previous_parse = parsing.FaceParsing.__call__
                previous_blend = blending.get_image
                previous_remove = os.remove
                try:
                    sys.argv = command[1:]
                    runpy.run_path(command[1], run_name="__main__")
                finally:
                    parsing.FaceParsing.__call__ = previous_parse
                    blending.get_image = previous_blend
                    os.remove = previous_remove
            return subprocess.CompletedProcess(command, 0)
        finally:
            sys.argv = previous
            os.chdir(cwd)
    return original_run(command, *args, **kwargs)


subprocess.run = resident_run


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        request = json.loads(self.rfile.readline())
        argv = request["argv"]
        try:
            sys.argv = argv
            with (
                Path(request["log"]).open("a") as log,
                contextlib.redirect_stdout(log),
                contextlib.redirect_stderr(log),
            ):
                runpy.run_path(argv[0], run_name="__main__")
            reply = {"ok": True}
        except BaseException:
            reply = {"ok": False, "error": traceback.format_exc()}
        self.wfile.write((json.dumps(reply) + "\n").encode())


class WorkerServer(socketserver.UnixStreamServer):
    def service_actions(self):
        if os.getppid() != parent_pid:
            raise SystemExit("Controller exited")


with WorkerServer(a.socket, Handler) as server:
    server.serve_forever()
