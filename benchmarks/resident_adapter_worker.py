"""Private Unix-socket worker retaining model factories across adapter calls.
Experimental: serial within each worker; does not change the deployed app.
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
a = p.parse_args()


def cached_factory(owner, name):
    original = getattr(owner, name)
    cache = {}

    def factory(*args, **kwargs):
        key = repr((args, sorted(kwargs.items())))
        if key not in cache:
            cache[key] = original(*args, **kwargs)
        return cache[key]

    setattr(owner, name, staticmethod(factory) if isinstance(owner, type) else factory)


if a.stage == "asr":
    import faster_whisper

    cached_factory(faster_whisper, "WhisperModel")
elif a.stage == "translate":
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    cached_factory(AutoTokenizer, "from_pretrained")
    cached_factory(AutoModelForSeq2SeqLM, "from_pretrained")
elif a.stage == "tts":
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    cached_factory(AutoTokenizer, "from_pretrained")
    cached_factory(ParlerTTSForConditionalGeneration, "from_pretrained")
elif a.stage == "lipsync":
    os.chdir(os.environ.get("MULTILINGUA_MUSETALK_REPO", str(Path.home() / "MuseTalk")))
    sys.path.insert(0, os.getcwd())
    import musetalk.utils.face_parsing as parsing
    import musetalk.utils.utils as muse_utils
    from transformers import WhisperModel

    cached_factory(muse_utils, "load_all_model")
    cached_factory(parsing, "FaceParsing")
    cached_factory(WhisperModel, "from_pretrained")
else:
    raise ValueError("Unsupported resident stage")
original_run = subprocess.run


def resident_run(command, *args, **kwargs):
    if a.stage == "lipsync" and command[1:3] == ["-m", "scripts.inference"]:
        previous = sys.argv
        cwd = os.getcwd()
        try:
            os.chdir(kwargs["cwd"])
            sys.argv = ["scripts.inference", *command[3:]]
            runpy.run_module("scripts.inference", run_name="__main__")
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


with socketserver.UnixStreamServer(a.socket, Handler) as server:
    server.serve_forever()
