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
                patch("multilingua.media.duration", return_value=3),
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

            with (
                patch("multilingua.media.fit_audio", side_effect=ValueError("too long")),
                patch("multilingua.media.duration", return_value=3),
            ):
                with self.assertRaisesRegex(ValueError, "BEFORE lip generation"):
                    Fake(config).render(root)
            self.assertEqual(texts, ["नमस्ते"] * 3)

    def test_rebalance_uses_shortest_take_with_matching_text_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            write_json(
                config,
                {
                    "commands": {"tts": ["python", "tts_parler.py"]},
                    "auto_compact_hindi": True,
                    "rebalance_speech_timing": True,
                },
            )
            original = "हम संपर्क कर रहे हैं और उन्हें जानकारी दे रहे हैं।"
            write_json(root / "job.json", {"duration": 1, "target_language": "hi"})
            write_json(
                root / "segments.json",
                [dict(start=0, end=1, text="We are contacting them.", translation=original)],
            )
            (root / "source.mp4").write_bytes(b"source")
            durations = iter([1.5, 1.8, 2.0, 2.2])

            class Fake(Pipeline):
                def adapter(self, stage, work, payload):
                    work.mkdir(exist_ok=True)
                    Path(payload["output"]).write_text(str(next(durations)))
                    write_json(work / "tts_request.json", payload)
                    write_json(work / "tts_response.json", {"spoken_text": payload["text"]})
                    return {}, 0.1

            def duration(path):
                return float(Path(path).read_text())

            def fit(src, dst, seconds, max_speed):
                raise ValueError(f"too long: {duration(src)}")

            with (
                patch("multilingua.media.duration", side_effect=duration),
                patch("multilingua.media.fit_audio", side_effect=fit),
                patch(
                    "multilingua.pipeline.rebalance", side_effect=ValueError("no room")
                ) as balance,
                patch("multilingua.media.cut") as cut,
            ):
                with self.assertRaisesRegex(ValueError, "too long: 1.5"):
                    Fake(config).render(root)
                cut.assert_not_called()
                self.assertEqual(balance.call_args.args[1], {0: 1.5})
                self.assertEqual(balance.call_args.args[0][0]["translation"], original)
            work = next(root.glob("renders/*/segment_0000"))
            self.assertEqual(duration(work / "raw.wav"), 1.5)
            self.assertEqual(read_json(work / "tts_request.json")["text"], original)
            self.assertEqual(read_json(work / "tts_response.json")["spoken_text"], original)
            report = read_json(work / "speech_preflight.json")
            self.assertEqual(report["selected_retry"], 0)
            self.assertTrue(report["text_unchanged"])
            self.assertEqual(read_json(work.parent / "timing_edits.json"), [])
