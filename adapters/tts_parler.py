"""Generic Hindi speaker generation; no reference voice or identity cloning."""
import argparse
import json
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--request', required=True)
p.add_argument('--response', required=True)
a = p.parse_args()
r = json.loads(Path(a.request).read_text())
if r.get('language', 'hi') not in ('hi','ta','te'):
    raise ValueError('Unsupported configured TTS language')
import torch
import soundfile as sf
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

started = time.monotonic()
device = r.get('device', 'cuda')
model_path = r['model']
precision = r.get('dtype', 'float32')
if precision not in ('float32', 'float16'):
    raise ValueError('TTS dtype must be float32 or float16')
if precision == 'float16' and not str(device).startswith('cuda'):
    raise ValueError('Half-precision TTS requires CUDA')
model = ParlerTTSForConditionalGeneration.from_pretrained(
    model_path, torch_dtype=getattr(torch, precision)).to(device).eval()
tokenizer = AutoTokenizer.from_pretrained(model_path)
description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
description = r.get('description', 'Rohit speaks in a mature male voice with a slightly low pitch and a calm, formal delivery at a moderately quick pace. Very clear audio, close recording, no background noise.')
d = description_tokenizer(description, return_tensors='pt').to(device)
loaded = time.monotonic()
rows = []
for item in r.get('items', [r]):
    torch.manual_seed(r.get('seed', 42))
    tokens = tokenizer(item['text'], return_tensors='pt').to(device)
    began = time.monotonic()
    with torch.inference_mode():
        generation = model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
            prompt_input_ids=tokens.input_ids, prompt_attention_mask=tokens.attention_mask,
            max_new_tokens=2048)
    audio = generation.float().cpu().numpy().squeeze()
    sr = model.config.sampling_rate
    Path(item['output']).parent.mkdir(parents=True, exist_ok=True)
    sf.write(item['output'], audio, sr)
    rows.append({'audio':item['output'], 'audio_seconds':len(audio)/sr,
                 'inference_seconds':time.monotonic()-began})
    print(json.dumps(rows[-1]), flush=True)
Path(a.response).write_text(json.dumps({'load_seconds':loaded-started, 'dtype':precision, 'voice_description':description,
    'items':rows, **(rows[0] if len(rows)==1 else {})}, indent=2))
