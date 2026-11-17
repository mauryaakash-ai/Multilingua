"""Same audio and references, two recognizers; never a substitute for listening."""
import gc,hashlib,json,sys,time
from pathlib import Path
from faster_whisper import WhisperModel
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from multilingua.evaluation import error_rates
out=root/'runs/evaluation/recognizer-comparison';out.mkdir(parents=True,exist_ok=True)
cases=[('rohit',root/'runs/hdtf-male-demo/dubbed.wav',root/'runs/evaluation/hindi-speech.json'),('divya',root/'runs/multispeaker/fd49928528ca4e9d8f8a6530f672e2f2/output.mp4',root/'runs/evaluation/hindi-speech-female.json')];rows=[]
for model_name in ['small','large-v3']:
 model=WhisperModel(str(root/f'models/faster-whisper-{model_name}'),device='cpu',compute_type='int8',cpu_threads=4)
 for name,audio,reference in cases:
  ref=json.loads(reference.read_text())['reference'];start=time.perf_counter();segments,info=model.transcribe(str(audio),language='hi',vad_filter=True,beam_size=5);hyp=' '.join(s.text.strip() for s in segments)
  row={'case':name,'recognizer':model_name,'audio':str(audio),'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'reference':ref,'hypothesis':hyp,'metrics':error_rates(ref,hyp),'inference_seconds':time.perf_counter()-start};rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True);(out/'report.json').write_text(json.dumps({'results':rows,'interpretation':'Recognizer disagreement estimates measurement sensitivity, not ground-truth TTS intelligibility. Native listening still required.'},indent=2,ensure_ascii=False))
 del model;gc.collect()
