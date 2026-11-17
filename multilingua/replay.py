"""Causal file replay: release chunks on source time; measure backlog explicitly.

This benchmark is intentionally distinct from webcam capture and continuous WebRTC output.
"""

import math
import queue
import threading
import time
import uuid
from pathlib import Path

from . import media
from .pipeline import Pipeline, write_json


def replay(config, source, output="runs", chunk_seconds=6, max_waiting=2, audio_only=False):
    if (
        not math.isfinite(chunk_seconds)
        or not 1 <= chunk_seconds <= 30
        or isinstance(max_waiting, bool)
        or not isinstance(max_waiting, int)
        or max_waiting < 1
    ):
        raise ValueError("Use 1–30 second chunks and at least one waiting slot")
    # Validate before starting a thread: an init failure in the worker otherwise looks like success.
    pipe = Pipeline(config)
    source = Path(source).resolve()
    streams = media.probe(source)["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    if video is None or not any(s["codec_type"] == "audio" for s in streams):
        raise ValueError("Replay input must contain video and audio")
    # Container duration can include trailing AAC padding after the last frame.
    total = media.video_duration(source)
    if total > 600:
        raise ValueError("Replay supports at most 10 minutes")
    folder = Path(output).resolve() / ("replay_" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    jobs = queue.Queue(maxsize=max_waiting)
    stop = threading.Event()
    rows, errors = [], []
    epoch = time.monotonic()

    def worker():
        while not stop.is_set():
            try:
                item = jobs.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                jobs.task_done()
                return
            index, path, start, end, arrived = item
            began = time.monotonic() - epoch
            try:
                job = pipe.prepare(path, folder / "jobs")
                rendered = pipe.render(job, audio_only=audio_only)
                ready = time.monotonic() - epoch
                rows.append(
                    {
                        "chunk": index,
                        "source_start": start,
                        "source_end": end,
                        "arrival_seconds": arrived,
                        "started_seconds": began,
                        "ready_seconds": ready,
                        "queue_seconds": began - arrived,
                        "source_end_to_ready_seconds": ready - end,
                        "compute_seconds": ready - began,
                        "output": str(rendered),
                    }
                )
                write_json(folder / "chunks.json", rows)
            except Exception as exc:
                errors.append(str(exc))
                stop.set()
            finally:
                jobs.task_done()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        for index in range(math.ceil(total / chunk_seconds)):
            start = index * chunk_seconds
            end = min(total, start + chunk_seconds)
            # No chunk is released to any neural adapter before its full window arrives.
            if stop.wait(max(0, end - (time.monotonic() - epoch))):
                break
            path = folder / f"input_{index:04d}.mp4"
            media.ffmpeg(
                "-ss",
                str(start),
                "-i",
                source,
                "-t",
                str(end - start),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                path,
            )
            try:
                jobs.put_nowait((index, path, start, end, time.monotonic() - epoch))
            except queue.Full:
                raise RuntimeError(
                    "Replay overloaded: bounded queue is full. No real-time claim is possible at this rate."
                )
        while thread.is_alive() and not stop.is_set():
            try:
                jobs.put(None, timeout=0.1)
                break
            except queue.Full:
                continue
        thread.join()
        if errors:
            raise RuntimeError(errors[0])
        delays = sorted(row["source_end_to_ready_seconds"] for row in rows)
        report = {
            "mode": "causal_file_replay",
            "status": "complete",
            "chunks": len(rows),
            "chunk_seconds": chunk_seconds,
            "audio_only": audio_only,
            "p50_ready_delay": delays[len(delays) // 2] if delays else None,
            "p95_ready_delay": delays[max(0, math.ceil(len(delays) * 0.95) - 1)]
            if delays
            else None,
            "note": "Ready delay includes whole-window waiting only relative to source end; not receiver playback latency.",
        }
        write_json(folder / "replay.json", report)
    except BaseException as exc:
        stop.set()
        # Let the active model subprocess terminate normally/at its configured timeout.
        thread.join()
        write_json(
            folder / "replay.json", {"status": "failed", "error": str(exc), "chunks": len(rows)}
        )
        raise
    return folder
