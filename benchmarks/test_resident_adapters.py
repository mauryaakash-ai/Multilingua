"""Validate cold then warm calls with original adapter request/response files."""
import json,socket,subprocess,tempfile,time,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];config=json.loads((root/'configs/generic-voice.local.json').read_text());fixture=json.loads((root/'runs/profiling/baseline/fixture.json').read_text());out=root/'runs/profiling/resident';out.mkdir(parents=True,exist_ok=True)
results=json.loads((out/'report.json').read_text()) if (out/'report.json').exists() else []
stages=sys.argv[1:] or ['asr','translate','tts','lipsync']
for stage in stages:
 command=[s.replace('{project}',str(root)) for s in config['commands'][stage]]
 if stage=='lipsync':command[0]='/home/akash/MuseTalk/.venv/bin/python'
 payload={'lipsync':{'video':fixture['video'],'audio':fixture['target_audio'],'output':str(out/'lips.mp4'),**{k:v for k,v in config['lipsync'].items() if k!='quality_mode'}},'asr':{'audio':fixture['source_audio'],'language':'en'},'translate':{'texts':[fixture['text']],'source':'eng_Latn','target':'hin_Deva'},'tts':{**config['tts'],'text':fixture['translation'],'output':str(out/'speech.wav')}}[stage]
 with tempfile.TemporaryDirectory(prefix='resident_') as tmp,(out/f'{stage}-worker.log').open('w') as log:
  sock=str(Path(tmp)/'worker.sock');began=time.perf_counter();proc=subprocess.Popen([command[0],str(root/'benchmarks/resident_adapter_worker.py'),'--socket',sock,'--stage',stage],cwd=root,stdout=log,stderr=subprocess.STDOUT)
  try:
   for _ in range(1200):
    if Path(sock).exists():break
    if proc.poll() is not None:raise RuntimeError(f'{stage} worker failed')
    time.sleep(.1)
   else:raise TimeoutError('Worker startup')
   startup=time.perf_counter()-began;times=[]
   for i in range(2):
    request=out/f'{stage}-{i}-request.json';response=out/f'{stage}-{i}-response.json';request.write_text(json.dumps(payload,ensure_ascii=False))
    argv=command[1:]+['--request',str(request),'--response',str(response)];start=time.perf_counter()
    with socket.socket(socket.AF_UNIX) as client:
     client.settimeout(300);client.connect(sock);client.sendall((json.dumps({'argv':argv,'log':str(out/f'{stage}.log')})+'\n').encode());reply=json.loads(client.makefile().readline())
    if not reply['ok']:raise RuntimeError(reply['error'])
    if not response.is_file():raise RuntimeError('Missing adapter response')
    times.append(time.perf_counter()-start)
   results.append({'stage':stage,'worker_import_seconds':startup,'cold_request_seconds':times[0],'warm_request_seconds':times[1],'pid':proc.pid})
   (out/'report.json').write_text(json.dumps(results,indent=2));print(results[-1],flush=True)
  finally:proc.terminate();proc.wait(timeout=15)
