"""Cold/warm complete 5-second jobs with all stage workers retained."""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from multilingua.pipeline import Pipeline, read_json
from multilingua.resident import ResidentPool

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="runs/profiling/integrated")
parser.add_argument("--tts-dtype", choices=["float32", "float16"], default="float32")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = (root / args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
pool = ResidentPool(out / "worker-logs")
stop = threading.Event()
memory = []


def sample():
    while not stop.is_set():
        try:
            memory.append(
                int(
                    subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                        text=True,
                    ).strip()
                )
            )
        except Exception:
            pass
        stop.wait(0.5)


t = threading.Thread(target=sample)
t.start()
rows = []
try:
    for index in range(2):
        p = Pipeline(root / "configs/local.json", resident_pool=pool)
        p.config["use_following_pause"] = True
        p.config["use_leading_pause"] = True
        p.config["tts"]["dtype"] = args.tts_dtype
        start = time.perf_counter()
        job = p.prepare(root / "runs/evaluation/service-input.mp4", out / "jobs")
        p.render(job)
        elapsed = time.perf_counter() - start
        state = read_json(job / "job.json")
        rows.append(
            {
                "index": index,
                "cold": index == 0,
                "elapsed_seconds": elapsed,
                "input_seconds": state["duration"],
                "rtf": elapsed / state["duration"],
                "job": str(job),
                "pids": {k: v[0].pid for k, v in pool.workers.items()},
                "stage_timings": state["timings"],
                "alignment": read_json(job / "alignment.json"),
            }
        )
        print(json.dumps(rows[-1]), flush=True)
        (out / "report.json").write_text(
            json.dumps(
                {"runs": rows, "peak_total_device_used_mib": max(memory) if memory else None},
                indent=2,
            )
        )
finally:
    stop.set()
    t.join()
    pool.close()
