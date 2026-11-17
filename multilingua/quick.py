"""Short local webcam previews, with an early translation and one voice synthesis call."""

import tempfile
import time
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import media
from .pipeline import Pipeline, write_json
from .timeline import subtitles

MAX_CLIP_SECONDS = 15


def warm_models(config, pool):
    """Load the three stage workers without submitting a user clip."""
    pipe = Pipeline(config, resident_pool=pool)
    with tempfile.TemporaryDirectory(prefix="multilingua-warmup-") as directory:
        job = Path(directory)
        with wave.open(str(job / "silence.wav"), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0" * 16000)
        requests = {
            "asr": {"audio": str(job / "silence.wav"), "language": "en", "beam_size": 1},
            "translate": {"texts": ["Hello."], "source": "eng_Latn", "target": "hin_Deva"},
            "tts": {
                **pipe.config.get("tts", {}),
                "language": "hi",
                "text": "नमस्ते।",
                "output": str(job / "warm.wav"),
            },
        }
        with ThreadPoolExecutor(max_workers=3) as threads:
            pending = [
                threads.submit(pipe.adapter, stage, job, payload)
                for stage, payload in requests.items()
                if pool.supports(stage, pipe.command(stage))
            ]
            for task in pending:
                task.result()


def quick_dub(clip, config, runs, pool=None):
    """Yield the draft text first, then a playable MP4 with a complete Hindi voice track."""
    started = time.monotonic()
    pipe = Pipeline(config, resident_pool=pool)
    job = Path(runs).resolve() / uuid.uuid4().hex
    job.mkdir(parents=True)
    source = Path(clip).resolve()
    data = media.probe(source)
    video = next((stream for stream in data["streams"] if stream["codec_type"] == "video"), None)
    if video is None or not any(s["codec_type"] == "audio" for s in data["streams"]):
        raise ValueError("Record a clip with the microphone enabled.")
    # Some webcam WebM files omit duration. Decode at most a small amount beyond the cap.
    english_audio = job / "english.wav"
    media.ffmpeg(
        "-i",
        source,
        "-map",
        "0:a:0",
        "-t",
        str(MAX_CLIP_SECONDS + 1),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        english_audio,
    )
    audio_seconds = media.duration(english_audio)
    reported_duration = video.get("duration") or data["format"].get("duration")
    source_seconds = (
        max(audio_seconds, float(reported_duration))
        if reported_duration not in (None, "N/A")
        else audio_seconds
    )
    if source_seconds > MAX_CLIP_SECONDS + 0.15:
        raise ValueError(f"Quick Webcam accepts clips up to {MAX_CLIP_SECONDS} seconds.")

    asr, asr_seconds = pipe.adapter(
        "asr", job, {"audio": str(english_audio), "language": "en", "beam_size": 1}
    )
    english = " ".join(row["text"].strip() for row in asr["segments"]).strip()
    if not english:
        raise ValueError("No speech detected. Check your microphone and try again.")
    mt, translation_seconds = pipe.adapter(
        "translate", job, {"texts": [english], "source": "eng_Latn", "target": "hin_Deva"}
    )
    (hindi,) = mt["texts"]
    if not isinstance(hindi, str) or not hindi.strip():
        raise ValueError("The translation model returned no Hindi text.")
    text_seconds = time.monotonic() - started
    yield {"english": english, "hindi": hindi, "text_seconds": text_seconds}

    raw_audio = job / "hindi.wav"
    _, tts_seconds = pipe.adapter(
        "tts",
        job,
        {**pipe.config.get("tts", {}), "text": hindi, "language": "hi", "output": str(raw_audio)},
    )
    if not raw_audio.is_file():
        raise RuntimeError("Speech model did not create an audio track.")
    speech_seconds = media.duration(raw_audio)
    output_seconds = max(speech_seconds, source_seconds)
    video_path = job / "quick-hindi.mp4"
    # Replace the English soundtrack. Hold the last frame if Hindi speech needs more time.
    media.ffmpeg(
        "-i",
        source,
        "-i",
        raw_audio,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        "scale=w='trunc(min(960,iw)/2)*2':h=-2,fps=25,tpad=stop_mode=clone:stop=-1",
        "-af",
        "apad",
        "-t",
        f"{output_seconds:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "4",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        video_path,
    )
    srt = job / "hindi.srt"
    srt.write_text(
        subtitles([{"start": 0.0, "end": speech_seconds, "translation": hindi}]), encoding="utf-8"
    )
    elapsed = time.monotonic() - started
    write_json(
        job / "quick.json",
        {
            "mode": "quick_webcam",
            "ai_dubbed": True,
            "lip_sync": False,
            "source_seconds": source_seconds,
            "output_seconds": media.duration(video_path),
            "translation_ready_seconds": text_seconds,
            "processing_seconds": elapsed,
            "asr_seconds": asr_seconds,
            "translation_seconds": translation_seconds,
            "tts_seconds": tts_seconds,
        },
    )
    yield {"video": str(video_path), "subtitles": str(srt), "seconds": elapsed}
