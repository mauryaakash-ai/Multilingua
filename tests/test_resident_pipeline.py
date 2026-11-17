import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from multilingua.pipeline import Pipeline, read_json, write_json


class ResidentPipelineTests(unittest.TestCase):
    def test_next_tts_overlaps_current_lipsync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            write_json(config, {"commands": {}, "overlap_tts": True})
            write_json(root / "job.json", {"duration": 2, "target_language": "hi"})
            write_json(
                root / "segments.json",
                [
                    {"start": 0, "end": 1, "text": "one", "translation": "एक"},
                    {"start": 1, "end": 2, "text": "two", "translation": "दो"},
                ],
            )
            (root / "source.mp4").write_bytes(b"source")
            next_tts = threading.Event()

            class Fake(Pipeline):
                def adapter(self, stage, work, payload):
                    Path(payload["output"]).write_bytes(b"media")
                    if stage == "tts" and work.name == "segment_0001":
                        next_tts.set()
                    if stage == "lipsync" and work.name == "segment_0000":
                        if not next_tts.wait(2):
                            raise AssertionError("Next phrase TTS did not overlap lip-sync")
                    return {}, 0.01

            pipe = Fake(config, resident_pool=object())

            def fit(src, dst, seconds, max_speed, *, extend_slot=False):
                Path(dst).write_bytes(b"audio")
                return {"raw_seconds": seconds, "slot_seconds": seconds, "speed": 1}

            with (
                patch(
                    "multilingua.media.probe",
                    return_value={"streams": [{"codec_type": "video", "duration": "2"}]},
                ),
                patch("multilingua.media.video_duration", return_value=1),
                patch("multilingua.media.cut"),
                patch("multilingua.media.fit_audio", side_effect=fit),
                patch(
                    "multilingua.media.duration",
                    side_effect=lambda p: 1 if Path(p).name == "lips.mp4" else 2,
                ),
                patch("multilingua.media.mux"),
                patch(
                    "multilingua.media.concatenate",
                    side_effect=lambda parts, out: Path(out).write_bytes(b"final"),
                ),
            ):
                self.assertEqual(pipe.render(root).read_bytes(), b"final")

    def test_silent_job_is_passthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            write_json(config, {"commands": {}})
            write_json(root / "job.json", {"duration": 3, "no_speech": True})
            (root / "source.mp4").write_bytes(b"original")
            with patch("multilingua.media.duration", return_value=3):
                self.assertEqual(Pipeline(config).render(root).read_bytes(), b"original")
            self.assertFalse(read_json(root / "job.json")["lip_sync"])
