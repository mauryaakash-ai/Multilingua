"""Reference-based text metrics and measured media checks; no invented ratings."""

import math
import unicodedata

from . import media


def normalized_words(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(" " if unicodedata.category(c).startswith("P") else c for c in text).split()


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def error_rates(reference, hypothesis):
    ref = normalized_words(reference)
    hyp = normalized_words(hypothesis)
    if not ref:
        raise ValueError("A nonempty independently checked reference is required")
    ref_chars = list("".join(ref))
    hyp_chars = list("".join(hyp))
    return {
        "wer": edit_distance(ref, hyp) / len(ref),
        "cer": edit_distance(ref_chars, hyp_chars) / len(ref_chars),
        "reference_words": len(ref),
        "normalization": "NFKC, casefold, punctuation as spaces; CER excludes whitespace",
    }


def media_checks(source, output):
    def info(path):
        p = media.probe(path)
        v = next(s for s in p["streams"] if s["codec_type"] == "video")
        a = next(s for s in p["streams"] if s["codec_type"] == "audio")
        return {
            "video_seconds": float(v["duration"]),
            "audio_seconds": float(a["duration"]),
            "frames": int(v["nb_frames"]) if v.get("nb_frames", "").isdigit() else None,
        }

    src = info(source)
    out = info(output)
    return {
        "source": src,
        "output": out,
        "video_drift_seconds": out["video_seconds"] - src["video_seconds"],
        "av_duration_difference_seconds": out["video_seconds"] - out["audio_seconds"],
        "preserved_frame_count": src["frames"] == out["frames"]
        if src["frames"] is not None and out["frames"] is not None
        else None,
    }


def percentiles(values):
    values = sorted(values)
    if not values or not all(math.isfinite(x) for x in values):
        raise ValueError("Finite measurements required")
    return {
        "n": len(values),
        "p50": values[max(0, math.ceil(0.5 * len(values)) - 1)],
        "p95": values[math.ceil(0.95 * len(values)) - 1],
    }
