"""All media operations use argument arrays, never shell interpolation."""

import json
import math
import subprocess


def run(args, timeout=600):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-3000:]}")
    return result.stdout


def probe(path):
    return json.loads(
        run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    )


def duration(path):
    value = float(probe(path)["format"]["duration"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Media duration must be positive and finite")
    return value


def video_duration(path):
    data = probe(path)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Media must contain video")
    value = float(video.get("duration") or data["format"]["duration"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Video duration must be positive and finite")
    return value


def ffmpeg(*args):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args])


def normalize(src, dst):
    data = probe(src)
    if not any(x["codec_type"] == "video" for x in data["streams"]):
        raise ValueError("Input must contain video")
    if not any(x["codec_type"] == "audio" for x in data["streams"]):
        raise ValueError("Input must contain audio")
    if duration(src) > 600:
        raise ValueError("Prototype supports clips up to 10 minutes")
    ffmpeg(
        "-i",
        src,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=25",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        dst,
    )


def extract_audio(src, dst):
    ffmpeg("-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst)


def cut(src, dst, start, seconds):
    ffmpeg(
        "-ss",
        f"{start:.6f}",
        "-i",
        src,
        "-t",
        f"{seconds:.6f}",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "25",
        dst,
    )


def fit_audio(src, dst, seconds, max_speed=1.25):
    if not math.isfinite(seconds) or seconds <= 0 or not 1 <= max_speed <= 1.25:
        raise ValueError("Use a positive finite slot and a speech speed cap between 1 and 1.25")
    actual = duration(src)
    ratio = actual / seconds
    if ratio > max_speed + 0.001:
        raise ValueError(
            f"Translation needs {actual:.2f}s but slot is {seconds:.2f}s. "
            "Shorten the reviewed translation; audio was not truncated."
        )
    speed = max(1.0, ratio)
    ffmpeg(
        "-i",
        src,
        "-af",
        f"atempo={speed:.8f},apad,atrim=duration={seconds:.8f}",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-c:a",
        "pcm_s16le",
        dst,
    )
    return {"raw_seconds": actual, "slot_seconds": seconds, "speed": speed}


def silence(dst, seconds):
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=24000:cl=mono",
        "-t",
        str(seconds),
        "-c:a",
        "pcm_s16le",
        dst,
    )


def mux(video, audio, dst, seconds):
    ffmpeg(
        "-i",
        video,
        "-i",
        audio,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        str(seconds),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        dst,
    )


def concatenate(parts, dst):
    if not parts:
        raise ValueError("No media parts to concatenate")
    inputs, filters, labels = [], [], []
    for i, part in enumerate(parts):
        inputs.extend(["-i", part])
        streams = probe(part)["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        seconds = float(video["duration"])
        filters.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
        filters.append(f"[{i}:a]atrim=duration={seconds:.8f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    filters.append("".join(labels) + f"concat=n={len(parts)}:v=1:a=1[v][a]")
    ffmpeg(
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        dst,
    )
