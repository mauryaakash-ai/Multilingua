"""Synthetic media test doubles verify orchestration, NEVER neural quality."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from multilingua import media
from multilingua.pipeline import Pipeline,read_json

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
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.video=self.root/'source with spaces.mp4'
        media.ffmpeg('-f','lavfi','-i','color=c=blue:s=160x120:r=25:d=2',
                     '-f','lavfi','-i','sine=frequency=500:duration=2',
                     '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',self.video)
        adapter=self.root/'fake.py';adapter.write_text(FAKE)
        cfg={'commands':{stage:[sys.executable,str(adapter),stage] for stage in ('asr','translate','tts','lipsync')}}
        config=self.root/'config.json';config.write_text(json.dumps(cfg));self.pipe=Pipeline(config)
    def tearDown(self): self.tmp.cleanup()
    def test_prepare_review_audio_only_and_timeline(self):
        job=self.pipe.prepare(self.video,self.root/'runs')
        self.assertEqual(read_json(job/'job.json')['status'],'awaiting_review')
        output=self.pipe.render(job,audio_only=True)
        self.assertTrue(output.is_file())
        self.assertAlmostEqual(media.duration(output),2,delta=0.2)
        self.assertFalse(read_json(job/'job.json')['lip_sync'])
        self.assertIn('नमस्ते',(job/'subtitles.srt').read_text())
        self.assertEqual(len(list(job.glob('part_*.mp4'))),3)
    def test_lip_failure_never_succeeds_as_passthrough(self):
        job=self.pipe.prepare(self.video,self.root/'runs')
        with self.assertRaises(RuntimeError): self.pipe.render(job)
        self.assertEqual(read_json(job/'job.json')['status'],'failed')
        self.assertFalse((job/'output.mp4').exists())
        self.assertFalse((job/'.render.lock').exists())
    def test_failed_rerender_preserves_completed_video(self):
        job=self.pipe.prepare(self.video,self.root/'runs')
        output=self.pipe.render(job,audio_only=True)
        original=output.read_bytes()
        with self.assertRaises(RuntimeError): self.pipe.render(job)
        self.assertEqual(output.read_bytes(),original)
        self.assertFalse((job/'output.pending.mp4').exists())

    def test_long_audio_rejected_without_truncation(self):
        src=self.root/'long.wav'
        media.ffmpeg('-f','lavfi','-i','sine=frequency=440:duration=2',src)
        with self.assertRaises(ValueError): media.fit_audio(src,self.root/'fit.wav',1)
    def test_moderate_speed_and_silence_fit(self):
        src=self.root/'audio.wav'
        media.ffmpeg('-f','lavfi','-i','sine=frequency=440:duration=1.2',src)
        result=media.fit_audio(src,self.root/'fit.wav',1)
        self.assertAlmostEqual(result['speed'],1.2,places=2)
        self.assertAlmostEqual(media.duration(self.root/'fit.wav'),1,delta=0.02)
    def test_lock_prevents_concurrent_render(self):
        job=self.pipe.prepare(self.video,self.root/'runs');(job/'.render.lock').touch()
        with self.assertRaises(FileExistsError): self.pipe.render(job,audio_only=True)
    def test_causal_replay_writes_real_media_and_metrics(self):
        from multilingua.replay import replay
        folder=replay(self.pipe.config_path,self.video,self.root/'replay',chunk_seconds=2,audio_only=True)
        report=read_json(folder/'replay.json')
        self.assertEqual(report['status'],'complete')
        row=read_json(folder/'chunks.json')[0]
        self.assertGreaterEqual(row['arrival_seconds'],2)
        self.assertTrue(Path(row['output']).is_file())

    def test_silent_video_rejected(self):
        silent=self.root/'silent.mp4'
        media.ffmpeg('-i',self.video,'-an','-c:v','copy',silent)
        with self.assertRaises(ValueError): self.pipe.prepare(silent,self.root/'runs')

    def test_subframe_tail_does_not_create_empty_video(self):
        job=self.pipe.prepare(self.video,self.root/'runs')
        review=job/'review.json'
        review.write_text(json.dumps([{'start':0,'end':1.98,'text':'Hello','translation':'नमस्ते'}]))
        output=self.pipe.render(job,review,audio_only=True)
        self.assertTrue(output.is_file())
        self.assertEqual(read_json(job/'reviewed_segments.json')[0]['end'],2.0)
        self.assertEqual(len(list(job.glob('part_*.mp4'))),1)

    def test_optional_following_pause_extends_slot(self):
        self.pipe.config['use_following_pause']=True
        job=self.pipe.prepare(self.video,self.root/'runs')
        self.pipe.render(job,audio_only=True)
        self.assertEqual(read_json(job/'requested_segments.json')[0]['end'],1.4)
        self.assertEqual(read_json(job/'reviewed_segments.json')[0]['end'],2.0)
        self.assertEqual(read_json(job/'job.json')['timing_policy'],'consume_following_pause')

    def test_optional_leading_pause_keeps_original_review(self):
        self.pipe.config.update(use_following_pause=True,use_leading_pause=True)
        job=self.pipe.prepare(self.video,self.root/'runs')
        self.pipe.render(job,audio_only=True)
        self.assertEqual(read_json(job/'requested_segments.json')[0]['start'],0.4)
        self.assertEqual(read_json(job/'reviewed_segments.json')[0]['start'],0)

if __name__=='__main__': unittest.main()
