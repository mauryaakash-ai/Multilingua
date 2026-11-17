"""Silero VAD phrase boundaries; silence returns an empty list successfully."""

import argparse
import json
from pathlib import Path

from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

p = argparse.ArgumentParser()
p.add_argument("--request", required=True)
p.add_argument("--response", required=True)
a = p.parse_args()
r = json.loads(Path(a.request).read_text())
audio = decode_audio(r["audio"], sampling_rate=16000)
options = VadOptions(
    min_speech_duration_ms=250,
    max_speech_duration_s=2,
    min_silence_duration_ms=300,
    speech_pad_ms=80,
)
segments = get_speech_timestamps(audio, options, sampling_rate=16000)
Path(a.response).write_text(
    json.dumps(
        {
            "segments": [{"start": s["start"] / 16000, "end": s["end"] / 16000} for s in segments],
            "silence": not bool(segments),
            "audio_seconds": len(audio) / 16000,
            "implementation": "faster-whisper bundled Silero ONNX",
            "note": "Bounded offline phrase detection; not yet WebRTC streaming.",
        },
        indent=2,
    )
)
