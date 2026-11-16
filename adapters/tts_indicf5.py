import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--response');a=p.parse_args()
r=json.loads(Path(a.request).read_text())
if r['language']!='hi': raise ValueError('This configured adapter is validated for Hindi inputs only')
if not Path(r.get('reference_audio','')).is_file() or not r.get('reference_text','').strip():
    raise ValueError('Set tts.reference_audio and its exact reference_text in local.json')
os.environ.setdefault('HF_MODULES_CACHE',str(Path(__file__).resolve().parents[1]/'models'/'modules'))
from transformers import AutoModel, AutoConfig
from safetensors.torch import load_file
from huggingface_hub import hf_hub_download
import time
import torch
import numpy as np
import soundfile as sf
started=time.monotonic()
model_id=r.get('model','ai4bharat/IndicF5')
config=AutoConfig.from_pretrained(model_id,trust_remote_code=True)
model=AutoModel.from_config(config,trust_remote_code=True)
checkpoint=Path(model_id)/'model.safetensors'
if not checkpoint.is_file():
    checkpoint=Path(hf_hub_download(model_id,'model.safetensors'))
# Transformers 4.x renames gamma/beta keys, corrupting this architecture's
# normalization weights. Load the original safetensors keys strictly instead.
weights=load_file(str(checkpoint),device='cpu')
model.load_state_dict(weights,strict=True)
del weights
model=model.to(r.get('device','cuda' if torch.cuda.is_available() else 'cpu')).eval()
loaded=time.monotonic()
if torch.cuda.is_available(): torch.cuda.reset_peak_memory_stats()
audio=model(r['text'],ref_audio_path=r['reference_audio'],ref_text=r['reference_text'])
if hasattr(audio,'detach'): audio=audio.detach().cpu().numpy()
audio=np.asarray(audio)
if audio.dtype==np.int16: audio=audio.astype(np.float32)/32768.0
sf.write(r['output'],audio,24000)
Path(a.response).write_text(json.dumps({'audio':r['output'],'load_seconds':loaded-started,'inference_seconds':time.monotonic()-loaded,'audio_seconds':len(audio)/24000,'strict_weights':True,'peak_cuda_bytes':torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None},indent=2))
