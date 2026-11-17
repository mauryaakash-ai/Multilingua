"""Authenticated single-operator GPU queue. Experimental webcam chunks, not real-time."""

import asyncio
import hmac
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .languages import language
from .pipeline import Pipeline, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def create_app(config=None, run_root=None, credentials=None, processor=None):
    username, password = credentials or (
        os.environ.get("MULTILINGUA_USER", ""),
        os.environ.get("MULTILINGUA_PASSWORD", ""),
    )
    if not username or len(password) < 16:
        raise RuntimeError("Set MULTILINGUA_USER and a password of at least 16 characters")
    config = config or os.environ.get("MULTILINGUA_CONFIG", str(ROOT / "configs/local.json"))
    folder = Path(
        run_root or os.environ.get("MULTILINGUA_RUNS", str(ROOT / "runs/server"))
    ).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    from .resident import ResidentPool

    pool = (
        ResidentPool(folder / "worker-logs")
        if os.environ.get("MULTILINGUA_RESIDENT") == "1" and processor is None
        else None
    )
    queue = asyncio.Queue(maxsize=1)
    active = None
    active_pipe = None
    uploading = False
    limit = 64 * 1024 * 1024
    auth = HTTPBasic()

    def verify(c: HTTPBasicCredentials = Depends(auth)):
        if not (
            hmac.compare_digest(c.username.encode(), username.encode())
            & hmac.compare_digest(c.password.encode(), password.encode())
        ):
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})

    def path_for(job_id):
        if not re.fullmatch("[0-9a-f]{32}", job_id):
            raise HTTPException(404, "Unknown job")
        path = folder / job_id
        if not (path / "state.json").is_file():
            raise HTTPException(404, "Unknown job")
        return path

    def process(path):
        nonlocal active_pipe
        if processor:
            return processor(path)
        pipe = Pipeline(config, resident_pool=pool) if pool else Pipeline(config)
        active_pipe = pipe
        if read_json(path / "state.json").get("cancel_requested"):
            pipe.cancel()
            raise RuntimeError("Job cancelled")
        target = read_json(path / "state.json").get("target_language", "hi")
        pipe.config["target_language"] = target
        if target != "hi":
            pipe.config["tts"] = {
                **pipe.config.get("tts", {}),
                "language": target,
                "description": language(target)["description"],
                "dtype": "float32",
            }
        if read_json(path / "state.json").get("model") == "latentsync":
            pipe.config["commands"]["lipsync"] = [
                sys.executable,
                str(ROOT / "adapters/lipsync_latentsync.py"),
            ]
            pipe.config["lipsync"] = {}
            pipe.config["timeout_seconds"] = 7200
        # Automatic webcam chunks may use the following pause to fit speech;
        # this never overlaps the next speech segment or raises the speed cap.
        pipe.config["overlap_tts"] = bool(pool)
        pipe.config["use_following_pause"] = True
        pipe.config["use_leading_pause"] = True
        job = pipe.prepare(path / "input.mp4", path / "work")
        result = pipe.render(job)
        shutil.copyfile(result, path / "output.mp4")
        shutil.copyfile(job / "segments.json", path / "segments.json")
        return {"speech_detected": not read_json(job / "job.json").get("no_speech", False)}

    async def worker():
        nonlocal active, active_pipe
        while True:
            path = await queue.get()
            active = path
            start = time.monotonic()
            state = read_json(path / "state.json")
            if state.get("cancel_requested"):
                active = None
                queue.task_done()
                continue
            try:
                state.update(status="processing")
                write_json(path / "state.json", state)
                details = await asyncio.to_thread(process, path)
                if isinstance(details, dict):
                    state.update(details)
                if not (path / "output.mp4").is_file():
                    raise RuntimeError("Worker produced no output")
                state.update(
                    status="cancelled"
                    if read_json(path / "state.json").get("cancel_requested")
                    else "complete",
                    compute_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                state.update(
                    status="cancelled"
                    if read_json(path / "state.json").get("cancel_requested")
                    else "failed",
                    error=str(exc),
                    compute_seconds=time.monotonic() - start,
                )
            finally:
                write_json(path / "state.json", state)
                active = None
                active_pipe = None
                queue.task_done()

    @asynccontextmanager
    async def lifespan(app):
        # A restarted service must not leave stale jobs appearing active forever.
        for f in folder.glob("*/state.json"):
            s = read_json(f)
            if s["status"] in ("queued", "processing"):
                s.update(status="failed", error="Server restarted before completion")
                write_json(f, s)
        task = asyncio.create_task(worker())
        yield
        await queue.join()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if pool:
            pool.close()

    app = FastAPI(
        lifespan=lifespan,
        dependencies=[Depends(verify)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.queue = queue

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web/index.html")

    @app.get("/api/status")
    def status():
        return {
            "mode": "experimental_chunked_webcam",
            "realtime_validated": False,
            "queued": queue.qsize(),
            "busy": active is not None,
            "max_upload_bytes": limit,
        }

    @app.post("/api/jobs", status_code=202)
    async def submit(request: Request):
        nonlocal uploading
        if request.headers.get("x-dubbing-consent") != "yes":
            raise HTTPException(400, "Permission confirmation required")
        if request.headers.get("content-type", "").split(";")[0] not in (
            "video/webm",
            "video/mp4",
            "application/octet-stream",
        ):
            raise HTTPException(415, "Send a complete WebM or MP4 file")
        target = request.headers.get("x-target-language", "hi")
        try:
            language(target)
        except ValueError:
            raise HTTPException(400, "Unsupported target language")
        model = request.headers.get("x-lipsync-model", "musetalk")
        if model not in ("musetalk", "latentsync"):
            raise HTTPException(400, "Unknown lip-sync model")
        if queue.full() or uploading:
            raise HTTPException(429, "GPU queue or upload slot full; stop capture and wait")
        uploading = True
        path = folder / uuid.uuid4().hex
        size = 0
        try:
            path.mkdir()
            with (path / "input.webm").open("wb") as f:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, "Maximum upload is 64 MiB")
                    f.write(chunk)
            if not size:
                raise HTTPException(400, "Empty upload")
            from . import media

            # Browser WebM often has no duration metadata. Remux/decode a bounded
            # prefix into a complete MP4, rejecting rather than accepting long clips.
            try:
                await asyncio.to_thread(
                    media.ffmpeg,
                    "-i",
                    path / "input.webm",
                    "-t",
                    "31",
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0",
                    "-vf",
                    "scale=w='trunc(min(1280,iw)/2)*2':h=-2,fps=25",
                    "-threads",
                    "2",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    path / "input.mp4",
                )
                seconds = await asyncio.to_thread(media.duration, path / "input.mp4")
            except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                raise HTTPException(422, "Upload must contain decodable video and audio") from exc
            # Allow a few milliseconds of browser audio/container padding.
            if seconds > 30.12:
                raise HTTPException(400, "Experimental server accepts clips up to 30 seconds")
            state = {
                "id": path.name,
                "status": "queued",
                "source_seconds": seconds,
                "created_unix": time.time(),
                "model": model,
                "target_language": target,
            }
            write_json(path / "state.json", state)
            try:
                queue.put_nowait(path)
            except asyncio.QueueFull:
                raise HTTPException(429, "GPU queue filled during upload; stop capture")
            return state
        except BaseException:
            shutil.rmtree(path, ignore_errors=True)
            raise
        finally:
            uploading = False

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return read_json(path_for(job_id) / "state.json")

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        path = path_for(job_id)
        state = read_json(path / "state.json")
        if state["status"] not in ("queued", "processing"):
            raise HTTPException(409, "Job is already finished")
        state.update(
            cancel_requested=True,
            status="cancelled" if state["status"] == "queued" else "processing",
        )
        write_json(path / "state.json", state)
        if active == path and active_pipe is not None:
            await asyncio.to_thread(active_pipe.cancel)
        return {"id": job_id, "cancel_requested": True}

    @app.get("/api/jobs/{job_id}/source")
    def source(job_id: str):
        path = path_for(job_id) / "input.mp4"
        if not path.is_file():
            raise HTTPException(404, "Original video unavailable")
        return FileResponse(path, media_type="video/mp4")

    @app.get("/api/jobs/{job_id}/output")
    def output(job_id: str):
        path = path_for(job_id)
        if read_json(path / "state.json")["status"] != "complete":
            raise HTTPException(409, "Output not ready")
        return FileResponse(path / "output.mp4", media_type="video/mp4")

    return app
