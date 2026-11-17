"""Export already-generated per-timeline-slot speech without altering published renders.

Use --speech-dir for the render attempt containing segment_XXXX/raw.wav.
This utility does not run or claim lip synchronization.
"""

import argparse
import sys
import uuid
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from multilingua import media
from multilingua.pipeline import read_json, write_json
from multilingua.timeline import frame_slots, subtitles, validate_segments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job")
    parser.add_argument("--source", help="Defaults to the normalized source.mp4 in the job")
    parser.add_argument(
        "--speech-dir", required=True, help="Render attempt with per-timeline-slot raw WAVs"
    )
    args = parser.parse_args()
    job = Path(args.job).resolve()
    speech = Path(args.speech_dir).resolve()
    source = Path(args.source).resolve() if args.source else job / "source.mp4"
    total = media.video_duration(source)
    segments = validate_segments(
        read_json(speech / "reviewed_segments.json"), total, translated=True
    )
    folder = job / "precomputed" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    alignment, files = [], []
    for index, segment in enumerate(frame_slots(segments, total)):
        seconds = segment["end"] - segment["start"]
        fitted = folder / f"fitted_{index:04d}.wav"
        if segment.get("translation", "").strip():
            raw = speech / f"segment_{index:04d}" / "raw.wav"
            stats = media.fit_audio(raw, fitted, seconds)
            alignment.append({"start": segment["start"], "end": segment["end"], **stats})
        else:
            media.silence(fitted, seconds)
        files.append(fitted)
    with wave.open(str(folder / "dubbed.wav"), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        for file in files:
            with wave.open(str(file), "rb") as inp:
                if (inp.getnchannels(), inp.getsampwidth(), inp.getframerate()) != (1, 2, 24000):
                    raise ValueError("Unexpected fitted WAV format")
                out.writeframes(inp.readframes(inp.getnframes()))
    media.mux(source, folder / "dubbed.wav", folder / "audio-only.mp4", total)
    if abs(media.duration(folder / "audio-only.mp4") - total) > 0.12:
        raise ValueError("Output duration drift")
    (folder / "subtitles.srt").write_text(subtitles(segments), encoding="utf-8")
    (folder / "AI-DUBBED.txt").write_text(
        "AI-dubbed Hindi audio-only comparison. Original lips retained.", encoding="utf-8"
    )
    write_json(folder / "alignment.json", alignment)
    print(folder / "audio-only.mp4")


if __name__ == "__main__":
    main()
