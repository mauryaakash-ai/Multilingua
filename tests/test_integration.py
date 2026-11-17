"""Synthetic media test doubles verify orchestration, NEVER neural quality."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from multilingua import media
from multilingua.pipeline import Pipeline, read_json

FAKE = r"""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--request');p.add_argument('--response');a=p.parse_args()
r=json.loads(Path(a.request).read_text())
if a.stage=='asr': out={'segments':[{'start':0.4,'end':1.4,'text':'Hello'}]}
elif a.stage=='translate': out={'texts':['नमस्ते']}
elif a.stage=='tts':
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.8',r['output']],check=True)
    out={'audio':r['output']}
else: raise RuntimeError('Deliberate failing lip adapter')
Path(a.response).write_text(json.dumps(out))
"""


class MediaIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.video = self.root / "source with spaces.mp4"
        media.ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x120:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            self.video,
        )
        adapter = self.root / "fake.py"
        adapter.write_text(FAKE)
        cfg = {
            "commands": {
                stage: [sys.executable, str(adapter), stage]
                for stage in ("asr", "translate", "tts", "lipsync")
            }
        }
        config = self.root / "config.json"
        config.write_text(json.dumps(cfg))
        self.pipe = Pipeline(config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_optional_enhancer_runs_after_lips_and_preserves_baseline(self):
        adapter = self.root / "fake.py"
        adapter.write_text(
            FAKE.replace(
                "else: raise RuntimeError('Deliberate failing lip adapter')",
                "else:\n    import shutil\n    shutil.copyfile(r['video'],r['output'])\n    out={'video':r['output'],'synthetic_test_only':True}",
            )
        )
        self.pipe.config["enhance_mouth"] = True
        self.pipe.config["commands"]["enhance"] = [sys.executable, str(adapter), "enhance"]
        job = self.pipe.prepare(self.video, self.root / "runs")
        output = self.pipe.render(job)
        self.assertTrue(output.is_file())
        self.assertTrue((job / "current" / "output.unenhanced.mp4").is_file())
        self.assertTrue(
            read_json(job / "provenance.json")["mouth_enhancement"]["synthetic_test_only"]
        )

    def test_audio_only_skips_optional_enhancer(self):
        self.pipe.config["enhance_mouth"] = True
        # No enhancer command configured: audio-only must never invoke it.
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job, audio_only=True)
        self.assertIsNone(read_json(job / "provenance.json")["mouth_enhancement"])

    def test_prepare_review_audio_only_and_timeline(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.assertEqual(read_json(job / "job.json")["status"], "awaiting_review")
        output = self.pipe.render(job, audio_only=True)
        self.assertTrue(output.is_file())
        self.assertAlmostEqual(media.duration(output), 2, delta=0.2)
        self.assertFalse(read_json(job / "job.json")["lip_sync"])
        self.assertIn("नमस्ते", (job / "subtitles.srt").read_text())
        self.assertEqual(len(list((job / "current").glob("part_*.mp4"))), 3)

    def test_lip_failure_never_succeeds_as_passthrough(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        with self.assertRaises(RuntimeError):
            self.pipe.render(job)
        self.assertEqual(read_json(job / "job.json")["status"], "failed")
        self.assertFalse((job / "output.mp4").exists())
        self.assertFalse((job / ".render.lock").exists())

    def test_failed_rerender_preserves_completed_video(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        output = self.pipe.render(job, audio_only=True)
        original = output.read_bytes()
        metadata = {
            name: (job / name).read_bytes()
            for name in (
                "subtitles.srt",
                "reviewed_segments.json",
                "alignment.json",
                "provenance.json",
            )
        }
        previous = read_json(job / "job.json")["published_render"]
        with self.assertRaises(RuntimeError):
            self.pipe.render(job)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(read_json(job / "job.json")["published_render"], previous)
        self.assertFalse(read_json(job / "job.json")["lip_sync"])
        for name, content in metadata.items():
            self.assertEqual((job / name).read_bytes(), content)
        self.assertFalse((job / "output.pending.mp4").exists())

    def test_config_cannot_override_reviewed_text_or_output(self):
        self.pipe.config["tts"] = {"text": "wrong text", "output": str(self.root / "wrong.wav")}
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job, audio_only=True)
        request = read_json(next((job / "current").glob("segment_*/tts_request.json")))
        self.assertEqual(request["text"], "नमस्ते")
        self.assertFalse((self.root / "wrong.wav").exists())
        import zipfile

        with zipfile.ZipFile(job / "delivery.zip") as bundle:
            self.assertIn("AI-DUBBED.txt", bundle.namelist())
            self.assertEqual(bundle.read("output.mp4"), (job / "output.mp4").read_bytes())

    def test_corrupt_state_still_releases_lock(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        (job / "job.json").write_text("broken")
        with self.assertRaises(ValueError):
            self.pipe.render(job, audio_only=True)
        self.assertFalse((job / ".render.lock").exists())

    def test_long_audio_rejected_without_truncation(self):
        src = self.root / "long.wav"
        media.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=2", src)
        with self.assertRaises(ValueError):
            media.fit_audio(src, self.root / "fit.wav", 1)

    def test_moderate_speed_and_silence_fit(self):
        src = self.root / "audio.wav"
        media.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1.2", src)
        result = media.fit_audio(src, self.root / "fit.wav", 1)
        self.assertAlmostEqual(result["speed"], 1.2, places=2)
        self.assertAlmostEqual(media.duration(self.root / "fit.wav"), 1, delta=0.02)

    def test_lock_prevents_concurrent_render(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        (job / ".render.lock").touch()
        with self.assertRaises(FileExistsError):
            self.pipe.render(job, audio_only=True)

    def test_causal_replay_writes_real_media_and_metrics(self):
        from multilingua.replay import replay

        folder = replay(
            self.pipe.config_path,
            self.video,
            self.root / "replay",
            chunk_seconds=2,
            audio_only=True,
        )
        report = read_json(folder / "replay.json")
        self.assertEqual(report["status"], "complete")
        row = read_json(folder / "chunks.json")[0]
        self.assertGreaterEqual(row["arrival_seconds"], 2)
        self.assertTrue(Path(row["output"]).is_file())

    def test_successful_lip_contract_with_explicit_test_double(self):
        # Passthrough is confined to this test: it establishes orchestration, never lip quality.
        adapter = self.root / "fake.py"
        adapter.write_text(
            FAKE.replace(
                "else: raise RuntimeError('Deliberate failing lip adapter')",
                "else:\n    import shutil\n    shutil.copyfile(r['video'], r['output'])\n    out={'video':r['output']}",
            )
        )
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job)
        self.assertTrue(read_json(job / "provenance.json")["lip_sync"])
        self.assertIn("lipsync_seconds", read_json(job / "alignment.json")[0])

    def test_many_fractional_slots_do_not_accumulate_drift(self):
        from multilingua.pipeline import write_json

        (self.root / "fake.py").write_text(FAKE.replace("duration=0.8", "duration=0.08"))
        job = self.pipe.prepare(self.video, self.root / "runs")
        segments = [
            dict(start=i / 10, end=(i + 1) / 10, text="Hello", translation="नमस्ते")
            for i in range(20)
        ]
        write_json(job / "segments.json", segments)
        self.pipe.render(job, audio_only=True)
        self.assertAlmostEqual(media.duration(job / "output.mp4"), 2, delta=0.12)

    def test_precomputed_export_does_not_mutate_published_bundle(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job, audio_only=True)
        original = (job / "alignment.json").read_bytes()
        script = Path(__file__).resolve().parents[1] / "scripts/render_precomputed.py"
        result = media.run([sys.executable, script, job, "--speech-dir", job / "current"]).strip()
        self.assertTrue(Path(result).is_file())
        self.assertEqual((job / "alignment.json").read_bytes(), original)
        self.assertAlmostEqual(media.duration(result), 2, delta=0.12)

    def test_silent_video_rejected(self):
        silent = self.root / "silent.mp4"
        media.ffmpeg("-i", self.video, "-an", "-c:v", "copy", silent)
        with self.assertRaises(ValueError):
            self.pipe.prepare(silent, self.root / "runs")

    def test_subframe_tail_does_not_create_empty_video(self):
        job = self.pipe.prepare(self.video, self.root / "runs")
        review = job / "review.json"
        review.write_text(
            json.dumps([{"start": 0, "end": 1.98, "text": "Hello", "translation": "नमस्ते"}])
        )
        output = self.pipe.render(job, review, audio_only=True)
        self.assertTrue(output.is_file())
        self.assertEqual(read_json(job / "reviewed_segments.json")[0]["end"], 2.0)
        self.assertEqual(len(list((job / "current").glob("part_*.mp4"))), 1)

    def test_optional_following_pause_extends_slot(self):
        self.pipe.config["use_following_pause"] = True
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job, audio_only=True)
        self.assertEqual(read_json(job / "requested_segments.json")[0]["end"], 1.4)
        self.assertEqual(read_json(job / "reviewed_segments.json")[0]["end"], 2.0)
        self.assertEqual(read_json(job / "job.json")["timing_policy"], "consume_following_pause")

    def test_optional_leading_pause_keeps_original_review(self):
        self.pipe.config.update(use_following_pause=True, use_leading_pause=True)
        job = self.pipe.prepare(self.video, self.root / "runs")
        self.pipe.render(job, audio_only=True)
        self.assertEqual(read_json(job / "requested_segments.json")[0]["start"], 0.4)
        self.assertEqual(read_json(job / "reviewed_segments.json")[0]["start"], 0)


if __name__ == "__main__":
    unittest.main()
