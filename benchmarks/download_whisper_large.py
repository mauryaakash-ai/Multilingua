"""Public official checkpoint download, validated ranges and LFS SHA256."""
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import HfApi,hf_hub_download
import requests,os,hashlib,time
from pathlib import Path
repo='Systran/faster-whisper-large-v3';name='model.bin';dest=Path('models/faster-whisper-large-v3')/name;dest.parent.mkdir(parents=True,exist_ok=True)
info=next(f for f in HfApi().model_info(repo,files_metadata=True).siblings if f.rfilename==name)
url=f'https://huggingface.co/{repo}/resolve/main/{name}?download=true';r=requests.get(url,stream=True,timeout=30);r.raise_for_status();url=r.url;r.close()
tmp=dest.with_suffix('.partial');fd=os.open(tmp,os.O_CREAT|os.O_RDWR,0o644);os.ftruncate(fd,info.size);chunk=16*1024*1024
def fetch(start):
 end=min(start+chunk,info.size)-1
 for attempt in range(4):
  try:
   r=requests.get(url,headers={'Range':f'bytes={start}-{end}'},timeout=(15,90));r.raise_for_status()
   if r.status_code!=206 or len(r.content)!=end-start+1 or not r.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):raise RuntimeError('Invalid range response')
   os.pwrite(fd,r.content,start);return
  except Exception:
   if attempt==3:raise
   time.sleep(2)
try:
 with ThreadPoolExecutor(max_workers=8) as ex:
  for i,_ in enumerate(ex.map(fetch,range(0,info.size,chunk))):
   if i%16==0:print(f'{min((i+1)*chunk,info.size)}/{info.size}',flush=True)
finally:os.close(fd)
h=hashlib.sha256()
with tmp.open('rb') as f:
 for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
assert h.hexdigest()==info.lfs.sha256,'Checksum mismatch'
os.replace(tmp,dest);print('VERIFIED',h.hexdigest(),flush=True)
for filename in ['config.json','preprocessor_config.json','tokenizer.json','vocabulary.json']:hf_hub_download(repo,filename,local_dir=dest.parent)
