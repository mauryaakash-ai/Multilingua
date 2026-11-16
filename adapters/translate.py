import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--response')
p.add_argument('--model',default='ai4bharat/indictrans2-en-indic-dist-200M')
p.add_argument('--device',default='cpu');a=p.parse_args()
r=json.loads(Path(a.request).read_text())
os.environ.setdefault('HF_MODULES_CACHE', str(Path(__file__).resolve().parents[1]/'models'/'modules'))
import torch
from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor
processor=IndicProcessor(inference=True)
tokenizer=AutoTokenizer.from_pretrained(a.model,trust_remote_code=True)
model=AutoModelForSeq2SeqLM.from_pretrained(a.model,trust_remote_code=True).to(a.device).eval()
outputs=[]
for start in range(0,len(r['texts']),8):
    batch=processor.preprocess_batch(r['texts'][start:start+8],src_lang=r['source'],tgt_lang=r['target'])
    inputs=tokenizer(batch,truncation=False,padding=True,return_tensors='pt').to(a.device)
    if inputs['input_ids'].shape[1]>256:
        raise ValueError('Translation phrase exceeds 256 tokens; split the source segment')
    with torch.inference_mode():
        ids=model.generate(**inputs,max_new_tokens=256,num_beams=5)
    text=tokenizer.batch_decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=True)
    outputs.extend(processor.postprocess_batch(text,lang=r['target']))
Path(a.response).write_text(json.dumps({'texts':outputs},ensure_ascii=False))
