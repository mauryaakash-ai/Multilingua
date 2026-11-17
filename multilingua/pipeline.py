"""Reviewable offline orchestration with isolated, versioned render artifacts."""

import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import media
from .concise import compact_hindi
from .timing_fit import rebalance
from .config import ROOT, command, load_config
from .languages import language, validate_model_route
from .timeline import frame_slots, sentence_segments, subtitles, validate_segments


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    tmp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Pipeline:
    def __init__(self, config, resident_pool=None, progress=None):
        self.resident_pool = resident_pool
        self.cancelled = threading.Event()
        self._children = set()
        self._child_lock = threading.Lock()
        self.config_path = Path(config).resolve()
        self.config = load_config(self.config_path)
        self.progress = progress or (lambda fraction, message: None)

    def cancel(self):
        self.cancelled.set()
        with self._child_lock:
            for proc in self._children:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if self.resident_pool:
            self.resident_pool.cancel_all()

    def command(self, stage):
        return command(self.config, stage)

    def adapter(self, stage, job, payload):
        request, response = job / f"{stage}_request.json", job / f"{stage}_response.json"
        write_json(request, payload)
        response.unlink(missing_ok=True)
        # A response alone cannot validate a stale artifact from an earlier invocation.
        if stage in ("tts", "lipsync"):
            Path(payload["output"]).unlink(missing_ok=True)
        cmd = self.command(stage) + ["--request", str(request), "--response", str(response)]
        started = time.monotonic()
        log_path = job / f"{stage}.log"
        if self.cancelled.is_set():
            raise RuntimeError("Job cancelled")
        base_command = self.command(stage)
        timeout = self.config.get("timeout_seconds", 1800)
        if self.resident_pool and self.resident_pool.supports(stage, base_command):
            self.resident_pool.call(stage, base_command, request, response, log_path, timeout)
            returncode = 0
        else:
            if self.resident_pool and stage == "lipsync":
                self.resident_pool.evict(stage)
            with log_path.open("a", encoding="utf-8") as log:
                with self._child_lock:
                    if self.cancelled.is_set():
                        raise RuntimeError("Job cancelled")
                    proc = subprocess.Popen(
                        cmd,
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=os.name == "posix",
                    )
                    self._children.add(proc)
                try:
                    proc.wait(timeout=timeout)
                except BaseException as exc:
                    if os.name == "posix":
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        proc.kill()
                    proc.wait()
                    if isinstance(exc, subprocess.TimeoutExpired):
                        raise RuntimeError(f"{stage} timed out. Inspect {log_path}") from exc
                    raise
                finally:
                    with self._child_lock:
                        self._children.discard(proc)
            returncode = proc.returncode
        if self.cancelled.is_set():
            raise RuntimeError("Job cancelled")
        if returncode or not response.exists():
            raise RuntimeError(f"{stage} failed. Inspect {log_path}")
        result = read_json(response)
        if not isinstance(result, dict):
            raise ValueError(f"{stage} response must be a JSON object")
        return result, time.monotonic() - started

    def prepare(self, video, runs="runs"):
        job = Path(runs).resolve() / uuid.uuid4().hex
        job.mkdir(parents=True)
        state = {
            "status": "preparing",
            "mode": "offline",
            "timings": {},
            "source_language": "en",
            "target_language": self.config.get("target_language", "hi"),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        write_json(job / "job.json", state)
        try:
            validate_model_route(self.config)
            self.progress(0.05, "Normalizing video and extracting audio")
            t = time.monotonic()
            media.normalize(Path(video).resolve(), job / "source.mp4")
            media.extract_audio(job / "source.mp4", job / "source.wav")
            state["duration"] = media.video_duration(job / "source.mp4")
            state["timings"]["media"] = time.monotonic() - t
            self.progress(0.25, "Recognizing English speech")
            asr, state["timings"]["asr"] = self.adapter(
                "asr", job, {"audio": str(job / "source.wav"), "language": "en"}
            )
            if asr.get("segments") == []:
                write_json(job / "segments.json", [])
                state.update(status="awaiting_review", no_speech=True)
                return job
            segments = validate_segments(asr.get("segments"), state["duration"])
            write_json(job / "asr_segments.json", segments)
            if self.config.get("group_sentences", True):
                segments = sentence_segments(segments)
                validate_segments(segments, state["duration"])
            self.progress(0.6, "Translating speech")
            mt, state["timings"]["translation"] = self.adapter(
                "translate",
                job,
                {
                    "texts": [s["text"] for s in segments],
                    "source": "eng_Latn",
                    "target": language(state["target_language"])["translation_target"],
                },
            )
            texts = mt.get("texts")
            if not isinstance(texts, list) or len(texts) != len(segments):
                raise ValueError("Translation response must contain one text per ASR segment")
            for segment, translated in zip(segments, texts):
                segment["translation"] = translated
            validate_segments(segments, state["duration"], translated=True)
            write_json(job / "segments.json", segments)
            state["status"] = "awaiting_review"
            self.progress(1, "Ready for bilingual review")
        except BaseException as exc:
            state.update(status="failed", error=str(exc) or type(exc).__name__)
            raise
        finally:
            write_json(job / "job.json", state)
        return job

    def render(self, job, review=None, audio_only=False):
        job = Path(job).resolve()
        lock = job / ".render.lock"
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        state = None
        started = time.monotonic()
        attempt = job / "renders" / uuid.uuid4().hex
        prefetch = None
        try:
            state = read_json(job / "job.json")
            silent = bool(state.get("no_speech"))
            requested = (
                []
                if silent
                else validate_segments(
                    read_json(review or job / "segments.json"), state["duration"], translated=True
                )
            )
            segments = requested
            if self.config.get("use_following_pause"):
                segments = [
                    {
                        **row,
                        "end": segments[i + 1]["start"]
                        if i + 1 < len(segments)
                        else state["duration"],
                    }
                    for i, row in enumerate(segments)
                ]
            if self.config.get("use_leading_pause") and segments:
                segments = [{**segments[0], "start": 0.0}, *segments[1:]]
            state["timing_policy"] = (
                "consume_following_pause"
                if self.config.get("use_following_pause")
                else "preserve_pauses"
            )
            state["use_leading_pause"] = bool(self.config.get("use_leading_pause"))
            timeline = [] if silent else list(frame_slots(segments, state["duration"]))
            segments = [row for row in timeline if row.get("translation", "").strip()]
            attempt.mkdir(parents=True)
            write_json(attempt / "requested_segments.json", requested)
            write_json(attempt / "reviewed_segments.json", segments)
            state.update(status="rendering", active_render=str(attempt.relative_to(job)))
            state.pop("error", None)
            write_json(job / "job.json", state)
            parts, alignment = [], []

            def synthesize(index, overrides=None):
                row = timeline[index]
                if not row.get("translation", "").strip():
                    return None
                work = attempt / f"segment_{index:04d}"
                work.mkdir(exist_ok=True)
                return self.adapter(
                    "tts",
                    work,
                    {
                        **self.config.get("tts", {}),
                        **(overrides or {}),
                        "text": row["translation"],
                        "language": state.get("target_language", "hi"),
                        "output": str(work / "raw.wav"),
                    },
                )

            # Recorded-video preflight: no lip work until EVERY speech slot fits.
            prepared = {}
            timing_edits = []
            timing_adjustments = []
            speech_costs = {}
            failures = []
            preflight = self.config.get("speech_preflight", True)
            if preflight:
                for index, row in enumerate(timeline):
                    if not row.get("translation", "").strip():
                        continue
                    if self.cancelled.is_set():
                        raise RuntimeError("Job cancelled")
                    self.progress(0.4 * index / max(1, len(timeline)),
                                  f"Checking speech timing {index + 1}/{len(timeline)} before lip generation")
                    work = attempt / f"segment_{index:04d}"
                    slot = row["end"] - row["start"]
                    elapsed = 0.0
                    candidates = []
                    # Retry delivery only: never silently change approved words.
                    retries = 2 if self.config.get("speech_delivery_retry", True) and any(
                        str(x).endswith("tts_parler.py") for x in self.config.get("commands", {}).get("tts", [])
                    ) else 0
                    original_text = row["translation"]
                    compact = compact_hindi(original_text) if self.config.get("auto_compact_hindi", False) and state.get("target_language", "hi") == "hi" else original_text
                    compact_retry = retries + 1 if compact != original_text else None
                    for retry in range(retries + 1 + (compact_retry is not None)):
                        overrides = None
                        if retry == compact_retry:
                            row["translation"] = compact
                        elif retry:
                            base = self.config.get("tts", {}).get("description", "Rohit speaks clearly in Hindi.")
                            overrides = {"description": base + (
                                " Speak briskly and fluently, with short pauses and clear pronunciation."
                                if retry == 1 else
                                " Deliver the sentence quickly and clearly in one continuous breath, without long pauses."
                            )}
                        _, took = synthesize(index, overrides)
                        elapsed += took
                        candidate = work / f"speech_candidate_{retry}.wav"
                        shutil.copyfile(work / "raw.wav", candidate)
                        try:
                            fitted = media.fit_audio(work / "raw.wav", work / "audio.wav", slot,
                                                     self.config.get("max_speech_speed", 1.25))
                        except ValueError as exc:
                            candidates.append({"retry": retry, "status": "too_long", "error": str(exc)})
                        else:
                            candidates.append({"retry": retry, "status": "fits", **fitted})
                            prepared[index] = (elapsed, fitted)
                            if row["translation"] != original_text:
                                timing_edits.append({"start": row["start"], "end": row["end"], "original": original_text, "replacement": row["translation"], "human_review": "pending"})
                            break
                    speech_costs[index] = elapsed
                    write_json(work / "speech_preflight.json", {"start": row["start"], "end": row["end"],
                               "text_unchanged": row["translation"] == original_text, "original_text": original_text, "generated_text": row["translation"], "candidates": candidates})
                    if index not in prepared:
                        failures.append({"start": row["start"], "end": row["end"], "translation": row["translation"],
                                         "reason": candidates[-1]["error"]})
                if failures and self.config.get("rebalance_speech_timing", False):
                    raw_durations = {i: media.duration(attempt / f"segment_{i:04d}" / "raw.wav") for i in speech_costs}
                    try:
                        adjusted = rebalance(timeline, raw_durations,
                                             max_speed=self.config.get("max_speech_speed", 1.25))
                    except ValueError:
                        pass  # Preserve the detailed per-phrase failure report.
                    else:
                        for i in speech_costs:
                            before, after = timeline[i], adjusted[i]
                            if (before["start"], before["end"]) != (after["start"], after["end"]):
                                timing_adjustments.append({"segment": i, "original_start": before["start"],
                                    "original_end": before["end"], "start": after["start"], "end": after["end"]})
                            work = attempt / f"segment_{i:04d}"
                            fitted = media.fit_audio(work / "raw.wav", work / "audio.wav",
                                                     after["end"] - after["start"], self.config.get("max_speech_speed", 1.25))
                            prepared[i] = (speech_costs[i], fitted)
                            detail = read_json(work / "speech_preflight.json")
                            detail.update(final_start=after["start"], final_end=after["end"],
                                          final_fit=fitted, timing_rebalanced=True)
                            write_json(work / "speech_preflight.json", detail)
                        timeline = adjusted
                        segments = [row for row in timeline if row.get("translation", "").strip()]
                        failures = []
                write_json(attempt / "timing_adjustments.json", timing_adjustments)
                write_json(attempt / "speech_preflight.json", {"passed": not failures, "failures": failures,
                           "lip_generation_started": False})
                write_json(attempt / "timing_edits.json", timing_edits)
                write_json(attempt / "reviewed_segments.json", segments)
                if failures:
                    summary = "; ".join(f"{r['start']:.2f}–{r['end']:.2f}s: {r['reason']}" for r in failures)
                    raise ValueError("Speech timing check failed BEFORE lip generation. " + summary)

            pending_tts = None
            if not preflight and timeline and self.resident_pool and self.config.get("overlap_tts"):
                prefetch = ThreadPoolExecutor(max_workers=1)
                pending_tts = prefetch.submit(synthesize, 0)
            for i, segment in enumerate(timeline):
                if self.cancelled.is_set():
                    raise RuntimeError("Job cancelled")
                synthesized = pending_tts.result() if pending_tts else None
                pending_tts = (
                    prefetch.submit(synthesize, i + 1)
                    if prefetch and i + 1 < len(timeline)
                    else None
                )
                self.progress(i / len(timeline), f"Rendering interval {i + 1} of {len(timeline)}")
                work = attempt / f"segment_{i:04d}"
                work.mkdir(exist_ok=True)
                seconds = segment["end"] - segment["start"]
                media.cut(job / "source.mp4", work / "video.mp4", segment["start"], seconds)
                speech = bool(segment.get("translation", "").strip())
                if speech:
                    _, elapsed = (None, prepared[i][0]) if preflight else (synthesized if synthesized is not None else synthesize(i))
                    if not (work / "raw.wav").is_file():
                        raise RuntimeError("TTS did not create the requested WAV file")
                    try:
                        fitted = prepared[i][1] if preflight else media.fit_audio(
                            work / "raw.wav",
                            work / "audio.wav",
                            seconds,
                            self.config.get("max_speech_speed", 1.25),
                        )
                    except ValueError as exc:
                        raise ValueError(
                            f"Phrase at {segment['start']:.2f}–{segment['end']:.2f}s: {exc}"
                        ) from exc
                    alignment.append(
                        {
                            "segment": i,
                            "start": segment["start"],
                            "end": segment["end"],
                            **fitted,
                            "tts_seconds": elapsed,
                        }
                    )
                    if not audio_only:
                        _, elapsed = self.adapter(
                            "lipsync",
                            work,
                            {
                                **self.config.get("lipsync", {}),
                                "video": str(work / "video.mp4"),
                                "audio": str(work / "audio.wav"),
                                "output": str(work / "lips.mp4"),
                            },
                        )
                        if not (work / "lips.mp4").is_file():
                            raise RuntimeError("Lip model returned without creating a video")
                        if abs(media.video_duration(work / "lips.mp4") - seconds) > 0.1:
                            raise RuntimeError("Lip video duration differs from the scheduled slot")
                        alignment[-1]["lipsync_seconds"] = elapsed
                else:
                    media.silence(work / "audio.wav", seconds)
                visual = work / ("lips.mp4" if speech and not audio_only else "video.mp4")
                part = attempt / f"part_{i:04d}.mp4"
                media.mux(visual, work / "audio.wav", part, seconds)
                parts.append(part)
            self.progress(0.95, "Checking timing and packaging downloads")
            if self.cancelled.is_set():
                raise RuntimeError("Job cancelled")
            if silent:
                shutil.copyfile(job / "source.mp4", attempt / "output.mp4")
            else:
                media.concatenate(parts, attempt / "output.mp4")
            measured = media.duration(attempt / "output.mp4")
            if abs(measured - state["duration"]) > 0.12:
                raise RuntimeError("Output duration drift exceeds 120 ms")
            (attempt / "subtitles.srt").write_text(subtitles(segments), encoding="utf-8")
            write_json(attempt / "alignment.json", alignment)
            elapsed = time.monotonic() - started
            report = {
                "ai_dubbed": not silent,
                "target_language": state.get("target_language", "hi"),
                "lip_sync": not audio_only and not silent,
                "source_seconds": state["duration"],
                "output_seconds": measured,
                "render_seconds": elapsed,
                "render_rtf": elapsed / state["duration"],
                "python": platform.python_version(),
                "source_sha256": sha256(job / "source.mp4"),
                "output_sha256": sha256(attempt / "output.mp4"),
                "config_sha256": sha256(self.config_path),
                "human_quality_review": "pending",
                "automatic_timing_edits": timing_edits,
                "timing_adjustments": timing_adjustments,
                "note": "AI-dubbed output. Review meaning, voice and visual quality before sharing. "
                "Model revision/license records are supplied separately by the operator.",
            }
            if silent:
                report["note"] = (
                    "No speech detected. Original normalized video returned without dubbing."
                )
            write_json(attempt / "provenance.json", report)
            (attempt / "AI-DUBBED.txt").write_text(report["note"], encoding="utf-8")
            artifacts = [
                "output.mp4",
                "subtitles.srt",
                "reviewed_segments.json",
                "requested_segments.json",
                "alignment.json",
                "provenance.json",
                "AI-DUBBED.txt",
            ]
            with zipfile.ZipFile(attempt / "delivery.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for name in artifacts:
                    archive.write(attempt / name, name)
            # All aliases resolve through one atomic pointer, keeping video and metadata together.
            pointer = job / ".current.pending"
            pointer.unlink(missing_ok=True)
            pointer.symlink_to(attempt.relative_to(job), target_is_directory=True)
            pointer.replace(job / "current")
            for name in [*artifacts, "delivery.zip"]:
                alias = job / name
                if not alias.is_symlink():
                    pending = job / (name + ".pending")
                    pending.unlink(missing_ok=True)
                    pending.symlink_to(Path("current") / name)
                    pending.replace(alias)
            state.update(
                status="complete",
                lip_sync=not audio_only and not silent,
                published_render=str(attempt.relative_to(job)),
                output_seconds=measured,
                render_seconds=elapsed,
                render_rtf=elapsed / state["duration"],
            )
            self.progress(1, "AI-dubbed video ready for quality review")
        except BaseException as exc:
            if prefetch:
                self.cancel()
            if state is not None:
                state.update(status="failed", error=str(exc) or type(exc).__name__)
            raise
        finally:
            try:
                if prefetch:
                    prefetch.shutdown(wait=True, cancel_futures=True)
                if state is not None:
                    state.pop("active_render", None)
                    write_json(job / "job.json", state)
            finally:
                lock.unlink(missing_ok=True)
        return job / "output.mp4"
