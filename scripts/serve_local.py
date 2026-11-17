"""Start a localhost-only authenticated webcam test service."""
import json,os,secrets,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
folder=root/'.runtime';folder.mkdir(mode=0o700,exist_ok=True);path=folder/'local-login.json'
if not path.exists():
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump({'username':'local','password':secrets.token_urlsafe(24)},f)
c=json.loads(path.read_text());os.environ['MULTILINGUA_USER']=c['username'];os.environ['MULTILINGUA_PASSWORD']=c['password']
print(f'Local login credentials are stored in {path}',flush=True)
os.environ.setdefault('MULTILINGUA_RESIDENT','1')
import uvicorn
uvicorn.run('multilingua.server:create_app',factory=True,host='127.0.0.1',port=7861,workers=1)
