"""Same-phrase IndicF5 test with its shipped demo reference, no user voice cloning."""
import json,sys,time,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'runs/profiling/indicf5';out.mkdir(parents=True,exist_ok=True)
c=json.loads((root/'configs/lipsync.local.json').read_text());f=json.loads((root/'runs/profiling/baseline/fixture.json').read_text());r={**c['tts'],'language':'hi','text':f['translation'],'output':str(out/'speech.wav')};request=out/'request.json';request.write_text(json.dumps(r,ensure_ascii=False));sys.argv=['adapter','--request',str(request),'--response',str(out/'unused.json')]
source=(root/'adapters/tts_indicf5.py').read_text();prefix=source.split("audio=model(r['text']",1)[0];start=time.perf_counter();exec(compile(prefix,str(root/'adapters/tts_indicf5.py'),'exec'));torch.cuda.synchronize();load=time.perf_counter()-start;rows=[]
for i in range(10):
 torch.manual_seed(42);torch.cuda.synchronize();t=time.perf_counter()
 with torch.inference_mode():audio=model(r['text'],ref_audio_path=r['reference_audio'],ref_text=r['reference_text'])
 torch.cuda.synchronize();seconds=time.perf_counter()-t
 if hasattr(audio,'detach'):audio=audio.detach().cpu().numpy()
 sf.write(out/'speech.wav',audio,24000);rows.append({'iteration':i,'seconds':seconds,'audio_seconds':len(audio)/24000});print(rows[-1],flush=True)
(out/'report.json').write_text(json.dumps({'load_seconds_including_imports':load,'mean_warm_seconds':statistics.mean(x['seconds'] for x in rows[1:]),'mean_output_rtf':statistics.mean(x['seconds']/x['audio_seconds'] for x in rows[1:]),'peak_torch_allocated_bytes':torch.cuda.max_memory_allocated(),'reference':'Shipped IndicF5 PAN_F_HAPPY_00001 demo; different voice from Rohit, not a controlled voice-identity comparison','runs':rows},indent=2))
