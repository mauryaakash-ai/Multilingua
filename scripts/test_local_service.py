"""Real HTTP smoke test with an existing development clip; does not activate a camera."""
import base64,json,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
c=json.loads((root/'.runtime/local-login.json').read_text());auth='Basic '+base64.b64encode((c['username']+':'+c['password']).encode()).decode()
video=root/'runs/hdtf-audio-demo/segment_0000/video.mp4'
# The source segment is video-only; use the five-second speech interval with source audio.
import sys
sys.path.insert(0,str(root));from multilingua import media
out=root/'runs/evaluation/service-input.mp4';media.ffmpeg('-ss','3','-i',root/'runs/hdtf-first/source.mp4','-t','5','-c:v','libx264','-c:a','aac',out)
req=urllib.request.Request('http://127.0.0.1:7861/api/jobs',data=out.read_bytes(),headers={'Authorization':auth,'Content-Type':'video/mp4','X-Dubbing-Consent':'yes'},method='POST')
with urllib.request.urlopen(req,timeout=30) as r:state=json.load(r)
(root/'runs/evaluation/service-job.json').write_text(json.dumps(state,indent=2));print(state,flush=True)
start=time.monotonic()
while time.monotonic()-start<1800:
 time.sleep(5)
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:7861/api/jobs/'+state['id'],headers={'Authorization':auth}),timeout=10) as r:state=json.load(r)
 if state['status'] in ('complete','failed'):
  (root/'runs/evaluation/service-result.json').write_text(json.dumps(state,indent=2));print(state,flush=True)
  if state['status']=='failed':raise SystemExit(1)
  req=urllib.request.Request('http://127.0.0.1:7861/api/jobs/'+state['id']+'/output',headers={'Authorization':auth})
  with urllib.request.urlopen(req,timeout=20) as r:(root/'runs/evaluation/service-output.mp4').write_bytes(r.read())
  break
else:raise TimeoutError('Local smoke test did not finish')
