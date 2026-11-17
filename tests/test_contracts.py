"""Boundary regressions: broken adapters must never produce plausible success."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from multilingua.pipeline import Pipeline
from multilingua.timeline import frame_slots, validate_segments


class ContractTests(unittest.TestCase):
    def test_review_rejects_non_text_and_missing_speech(self):
        for invalid in (None, 123, [], {}, "", " "):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_segments(
                    [dict(start=0, end=1, text="Hello", translation=invalid)], 2, True
                )

    def test_invalid_shapes_and_timestamps(self):
        for segments in (
            {},
            [],
            ["hello"],
            [dict(start=True, end=1, text="Hello")],
            [dict(start=-0.0001, end=1, text="Hello")],
        ):
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                validate_segments(segments, 2)

    def test_frame_rounding_does_not_accumulate(self):
        segments = [
            dict(start=i / 10, end=(i + 1) / 10, text="A", translation="अ") for i in range(100)
        ]
        timeline = list(frame_slots(segments, 10))
        self.assertAlmostEqual(sum(x["end"] - x["start"] for x in timeline), 10)
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(timeline, timeline[1:])))

    def test_subframe_speech_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            list(frame_slots([dict(start=0, end=0.001, translation="अ")], 1))

    def test_adapter_removes_stale_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "adapter.py"
            script.write_text("import sys,pathlib; pathlib.Path(sys.argv[-1]).write_text('{}')")
            config = root / "config.json"
            config.write_text(json.dumps({"commands": {"tts": [sys.executable, str(script)]}}))
            output = root / "raw.wav"
            output.write_bytes(b"stale audio")
            Pipeline(config).adapter("tts", root, {"output": str(output)})
            self.assertFalse(output.exists())

    def test_adapter_timeout_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "commands": {"asr": [sys.executable, "-c", "import time; time.sleep(30)"]},
                        "timeout_seconds": 1,
                    }
                )
            )
            with self.assertRaisesRegex(RuntimeError, "asr timed out.*asr.log"):
                Pipeline(config).adapter("asr", root, {})

    def test_replay_configuration_failure_is_synchronous(self):
        from multilingua.replay import replay

        with self.assertRaisesRegex(ValueError, "Configuration not found"):
            replay("/nonexistent/config.json", "/nonexistent/video.mp4")
