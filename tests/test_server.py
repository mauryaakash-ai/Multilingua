import tempfile,time,unittest,threading
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from multilingua.server import create_app
class ServerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def app(self,processor=lambda p:(p/'output.mp4').write_bytes(b'demo')):
  return create_app(run_root=self.root,credentials=('tester','long-test-password'),processor=processor)
 def test_credentials_required(self):
  with self.assertRaises(RuntimeError):create_app(run_root=self.root,credentials=('',''))
 def test_auth_and_path_validation(self):
  with TestClient(self.app()) as c:
   self.assertEqual(c.get('/api/status').status_code,401)
   self.assertEqual(c.get('/api/status',auth=('tester','wrong')).status_code,401)
   self.assertFalse(c.get('/api/status',auth=('tester','long-test-password')).json()['realtime_validated'])
   self.assertEqual(c.get('/api/jobs/not-a-uuid',auth=('tester','long-test-password')).status_code,404)
 def test_complete_and_failed_jobs(self):
  for fail in (False,True):
   def process(p):
    if fail:raise ValueError('model failure')
    (p/'output.mp4').write_bytes(b'demo')
   with TestClient(self.app(process)) as c,patch('multilingua.media.ffmpeg'),patch('multilingua.media.duration',return_value=6):
    c.auth=('tester','long-test-password')
    r=c.post('/api/jobs',content=b'video',headers={'Content-Type':'video/webm','X-Dubbing-Consent':'yes'});self.assertEqual(r.status_code,202)
    key=r.json()['id']
    for _ in range(100):
     s=c.get('/api/jobs/'+key).json()
     if s['status'] in ('complete','failed'):break
     time.sleep(.01)
    self.assertEqual(s['status'],'failed' if fail else 'complete')
    self.assertEqual(c.get('/api/jobs/'+key+'/output').status_code,409 if fail else 200)
 def test_input_guards(self):
  with TestClient(self.app()) as c:
   c.auth=('tester','long-test-password')
   self.assertEqual(c.post('/api/jobs',content=b'x').status_code,400)
   self.assertEqual(c.post('/api/jobs',content=b'x',headers={'X-Dubbing-Consent':'yes','Content-Type':'text/plain'}).status_code,415)
   self.assertEqual(c.post('/api/jobs',content=b'',headers={'X-Dubbing-Consent':'yes','Content-Type':'video/webm'}).status_code,400)
 def test_long_clip_rejected(self):
  with TestClient(self.app()) as c,patch('multilingua.media.ffmpeg'),patch('multilingua.media.duration',return_value=31):
   c.auth=('tester','long-test-password')
   self.assertEqual(c.post('/api/jobs',content=b'x',headers={'X-Dubbing-Consent':'yes','Content-Type':'video/webm'}).status_code,400)
   self.assertFalse(list(self.root.iterdir()))
 def test_queue_bound(self):
  started=threading.Event();release=threading.Event()
  def process(p):
   started.set();release.wait(5);(p/'output.mp4').write_bytes(b'demo')
  with TestClient(self.app(process)) as c,patch('multilingua.media.ffmpeg'),patch('multilingua.media.duration',return_value=6):
   c.auth=('tester','long-test-password');headers={'X-Dubbing-Consent':'yes','Content-Type':'video/webm'}
   try:
    self.assertEqual(c.post('/api/jobs',content=b'x',headers=headers).status_code,202)
    self.assertTrue(started.wait(2))
    self.assertEqual(c.post('/api/jobs',content=b'x',headers=headers).status_code,202)
    self.assertEqual(c.post('/api/jobs',content=b'x',headers=headers).status_code,429)
   finally:release.set()
 def test_model_selection_routes_worker(self):
  seen=[]
  class FakePipeline:
   def __init__(self,config):self.config={'commands':{'lipsync':['original']}}
   def prepare(self,source,work):
    seen.append(self.config);work.mkdir();(work/'segments.json').write_text('[]');(work/'job.json').write_text('{}');return work
   def render(self,work):
    out=work/'output.mp4';out.write_bytes(b'demo');return out
  app=create_app(run_root=self.root,credentials=('tester','long-test-password'))
  with TestClient(app) as c,patch('multilingua.server.Pipeline',FakePipeline),patch('multilingua.media.ffmpeg'),patch('multilingua.media.duration',return_value=10):
   c.auth=('tester','long-test-password');headers={'Content-Type':'video/webm','X-Dubbing-Consent':'yes','X-Lipsync-Model':'unknown'}
   self.assertEqual(c.post('/api/jobs',content=b'x',headers=headers).status_code,400)
   for model in ('latentsync','musetalk'):
    headers['X-Lipsync-Model']=model;r=c.post('/api/jobs',content=b'x',headers=headers);self.assertEqual(r.status_code,202);self.assertEqual(r.json()['model'],model)
    for _ in range(100):
     status=c.get('/api/jobs/'+r.json()['id']).json()['status']
     if status in ('complete','failed'):break
     time.sleep(.01)
    self.assertEqual(status,'complete')
   self.assertIn('lipsync_latentsync.py',seen[0]['commands']['lipsync'][1])
   self.assertEqual(seen[0]['timeout_seconds'],7200)
   self.assertEqual(seen[1]['commands']['lipsync'],['original'])
 def test_queued_cancellation(self):
  started=threading.Event();release=threading.Event();processed=[]
  def process(p):
   processed.append(p.name);started.set();release.wait(3);(p/'output.mp4').write_bytes(b'demo')
  with TestClient(self.app(process)) as c,patch('multilingua.media.ffmpeg'),patch('multilingua.media.duration',return_value=6):
   c.auth=('tester','long-test-password');h={'Content-Type':'video/webm','X-Dubbing-Consent':'yes'}
   try:
    first=c.post('/api/jobs',content=b'x',headers=h).json()['id'];self.assertTrue(started.wait(2))
    second=c.post('/api/jobs',content=b'x',headers=h).json()['id']
    self.assertEqual(c.post('/api/jobs/'+second+'/cancel').status_code,200)
    self.assertEqual(c.get('/api/jobs/'+second).json()['status'],'cancelled')
    self.assertEqual(c.get('/api/jobs/'+second+'/output').status_code,409)
   finally:release.set()
  self.assertEqual(processed,[first])
 def test_unknown_target_language(self):
  with TestClient(self.app()) as c:
   c.auth=('tester','long-test-password')
   self.assertEqual(c.post('/api/jobs',content=b'x',headers={'Content-Type':'video/webm','X-Dubbing-Consent':'yes','X-Target-Language':'invalid'}).status_code,400)
