"""Isolated-environment resident-stage benchmark: 10 calls, first excluded."""
import argparse,json,os,statistics,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--stage',choices=['asr','translation','tts','musetalk','ffmpeg'],required=True);p.add_argument('--tts-dtype',choices=['float32','float16'],default='float32');p.add_argument('--batch-size',type=int,default=2);p.add_argument('--fixture',required=True);p.add_argument('--output',required=True);a=p.parse_args()
r=json.loads(Path(a.fixture).read_text());torch=None;load_start=time.perf_counter();device='cpu';components={}
def sync():
 if torch is not None and device=='cuda':torch.cuda.synchronize()
def measure(fn):
 sync();t=time.perf_counter();v=fn();sync();return v,time.perf_counter()-t
if a.stage=='asr':
 from faster_whisper import WhisperModel
 model=WhisperModel(r['asr_model'],device='cpu',compute_type='int8',cpu_threads=4)
 def infer():
  seg,info=model.transcribe(r['source_audio'],language='en',vad_filter=True,beam_size=5)
  return {'text':' '.join(s.text for s in seg),'audio_seconds':info.duration}
elif a.stage=='translation':
 import torch
 torch.set_num_threads(4)
 os.environ['HF_MODULES_CACHE']=r['modules_cache']
 from transformers import AutoModelForSeq2SeqLM,AutoTokenizer
 from IndicTransToolkit import IndicProcessor
 tokenizer=AutoTokenizer.from_pretrained(r['translation_model'],trust_remote_code=True)
 model=AutoModelForSeq2SeqLM.from_pretrained(r['translation_model'],trust_remote_code=True).eval()
 processor=IndicProcessor(inference=True)
 def infer():
  batch=processor.preprocess_batch([r['text']],src_lang='eng_Latn',tgt_lang='hin_Deva');x=tokenizer(batch,return_tensors='pt',padding=True)
  with torch.inference_mode():ids=model.generate(**x,max_new_tokens=256,num_beams=5)
  return {'text':processor.postprocess_batch(tokenizer.batch_decode(ids,skip_special_tokens=True),lang='hin_Deva')[0]}
elif a.stage=='tts':
 import torch
 torch.set_num_threads(4);device='cuda'
 from parler_tts import ParlerTTSForConditionalGeneration
 from transformers import AutoTokenizer
 model=ParlerTTSForConditionalGeneration.from_pretrained(r['tts_model'],torch_dtype=getattr(torch,a.tts_dtype)).to(device).eval()
 tokenizer=AutoTokenizer.from_pretrained(r['tts_model']);dt=AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
 d=dt(r['description'],return_tensors='pt').to(device)
 def infer():
  torch.manual_seed(42);x=tokenizer(r['translation'],return_tensors='pt').to(device)
  with torch.inference_mode():y=model.generate(input_ids=d.input_ids,attention_mask=d.attention_mask,prompt_input_ids=x.input_ids,prompt_attention_mask=x.attention_mask,max_new_tokens=2048)
  audio=y.float().cpu().numpy().squeeze()
  import soundfile as sf
  sf.write(Path(a.output).with_suffix('.wav'),audio,model.config.sampling_rate)
  return {'audio_seconds':len(audio)/model.config.sampling_rate}
elif a.stage=='musetalk':
 os.chdir(r['musetalk_repo']);sys.path.insert(0,r['musetalk_repo'])
 import torch,cv2,numpy as np
 torch.set_num_threads(4);device='cuda'
 from musetalk.utils.utils import load_all_model,datagen
 from musetalk.utils.preprocessing import get_landmark_and_bbox
 from musetalk.utils.audio_processor import AudioProcessor
 from musetalk.utils.face_parsing import FaceParsing
 from musetalk.utils.blending import get_image
 from transformers import WhisperModel
 vae,unet,pe=load_all_model(device=torch.device(device));vae.vae=vae.vae.half().to(device);unet.model=unet.model.half().to(device);pe=pe.half().to(device)
 audio_processor=AudioProcessor('models/whisper');whisper=WhisperModel.from_pretrained('models/whisper').half().to(device).eval();fp=FaceParsing(left_cheek_width=90,right_cheek_width=90)
 timestep=torch.tensor([0],device=device)
 def infer():
  timings={}
  def read_frames():
   cap=cv2.VideoCapture(r['video']);frames=[]
   while True:
    ok,frame=cap.read()
    if not ok:break
    frames.append(frame)
   cap.release();return frames
  frames,timings['frame_decode']=measure(read_frames)
  # Upstream landmark utility accepts file paths, so use fixed extracted frames.
  (coords,frames),timings['face_detection']=measure(lambda:get_landmark_and_bbox(r['frame_paths'],0))
  def encode():
   latents=[]
   for box,frame in zip(coords,frames):
    x1,y1,x2,y2=box
    if tuple(box)==(0,0,0,0):raise RuntimeError('Face missing')
    crop=cv2.resize(frame[y1:min(y2+10,frame.shape[0]),x1:x2],(256,256),interpolation=cv2.INTER_LANCZOS4)
    latents.append(vae.get_latents_for_unet(crop))
   return latents
  with torch.inference_mode():
   latents,timings['vae_encode']=measure(encode)
   def audio():
    features,length=audio_processor.get_audio_feature(r['target_audio']);return audio_processor.get_whisper_chunk(features,device,torch.float16,whisper,length,fps=25)
   chunks,timings['audio_features']=measure(audio)
   def render():
    faces=[]
    for wb,lb in datagen(chunks,latents,batch_size=a.batch_size,device=device):
     y=unet.model(lb.half(),timestep,encoder_hidden_states=pe(wb)).sample;faces.extend(vae.decode_latents(y))
    return faces
   faces,timings['unet_and_decode']=measure(render)
   def blend():
    for i,face in enumerate(faces):
     frame=frames[i%len(frames)];x1,y1,x2,y2=coords[i%len(coords)];y2=min(y2+10,frame.shape[0]);res=cv2.resize(face.astype(np.uint8),(x2-x1,y2-y1));get_image(frame.copy(),res,[x1,y1,x2,y2],mode='jaw',fp=fp)
   _,timings['face_parse_and_blend']=measure(blend)
  return {'components_seconds':timings,'frames':len(faces),'audio_seconds':r['target_seconds']}
else:
 def infer():
  subprocess.run(['ffmpeg','-v','error','-y','-i',r['video'],'-i',r['target_audio'],'-map','0:v:0','-map','1:a:0','-t',str(r['source_seconds']),'-c:v','libx264','-crf','18','-c:a','aac',str(Path(a.output).with_suffix('.mp4'))],check=True)
  return {}
sync();load_seconds=time.perf_counter()-load_start
if torch is not None and device=='cuda':torch.cuda.reset_peak_memory_stats()
rows=[]
for i in range(10):
 result,seconds=measure(infer);duration=result.get('audio_seconds',r['source_seconds']);rows.append({'iteration':i,'warmup':i==0,'seconds':seconds,'audio_seconds':duration,'rtf':seconds/duration,**result});print(json.dumps({'stage':a.stage,'iteration':i,'seconds':seconds}),flush=True)
report={'stage':a.stage,'device':device,'load_seconds_including_imports':load_seconds,'warmup_seconds':rows[0]['seconds'],'mean_inference_seconds':statistics.mean(x['seconds'] for x in rows[1:]),'mean_rtf':statistics.mean(x['rtf'] for x in rows[1:]),'peak_torch_allocated_bytes':torch.cuda.max_memory_allocated() if torch is not None and device=='cuda' else None,'peak_torch_reserved_bytes':torch.cuda.max_memory_reserved() if torch is not None and device=='cuda' else None,'runs':rows,'notes':'Ten calls in one process; first excluded. CUDA synchronized around GPU timing. Individual stage memory, not simultaneous residency. CPU stages intentionally retain baseline device. FFmpeg measures final encode/mux only.'}
Path(a.output).write_text(json.dumps(report,indent=2,ensure_ascii=False))
