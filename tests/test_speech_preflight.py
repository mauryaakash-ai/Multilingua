import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multilingua.pipeline import Pipeline, read_json, write_json


class SpeechPreflightTests(unittest.TestCase):
    def test_later_timing_failure_never_starts_lips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            write_json(config, {"commands": {}})
            write_json(root / "job.json", {"duration": 2, "target_language": "hi"})
            write_json(
                root / "segments.json",
                [
                    dict(start=0, end=1, text="First.", translation="एक"),
                    dict(start=1, end=2, text="Second.", translation="दो"),
                ],
            )
            (root / "source.mp4").write_bytes(b"source")
            calls = []

            class Fake(Pipeline):
                def adapter(self, stage, work, payload):
                    calls.append(stage)
                    Path(payload["output"]).write_bytes(b"audio")
                    return {}, 0.1

            def fit(src, dst, *args):
                if src.parent.name == "segment_0001":
                    raise ValueError("Translation needs 3s but slot is 1s")
                Path(dst).write_bytes(b"fitted")
                return dict(raw_seconds=1, slot_seconds=1, speed=1)

            with (
                patch("multilingua.media.fit_audio", side_effect=fit),
                patch("multilingua.media.cut") as cut,
            ):
                with self.assertRaisesRegex(ValueError, "BEFORE lip generation"):
                    Fake(config).render(root)
                cut.assert_not_called()
            self.assertEqual(calls, ["tts", "tts"])
            self.assertFalse((root / "output.mp4").exists())
            report = read_json(next(root.glob("renders/*/speech_preflight.json")))
            self.assertEqual(len(report["failures"]), 1)
            self.assertFalse(report["lip_generation_started"])

    def test_delivery_retry_is_bounded_and_keeps_reviewed_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            write_json(config, {"commands": {"tts": ["python", "tts_parler.py"]}})
            write_json(root / "job.json", {"duration": 1, "target_language": "hi"})
            write_json(
                root / "segments.json", [dict(start=0, end=1, text="Hello.", translation="नमस्ते")]
            )
            (root / "source.mp4").write_bytes(b"source")
            texts = []

            class Fake(Pipeline):
                def adapter(self, stage, work, payload):
                    texts.append(payload["text"])
                    Path(payload["output"]).write_bytes(b"audio")
                    return {}, 0.1

            with patch("multilingua.media.fit_audio", side_effect=ValueError("too long")):
                with self.assertRaisesRegex(ValueError, "BEFORE lip generation"):
                    Fake(config).render(root)
            self.assertEqual(texts, ["नमस्ते"] * 3)
