"""Private resident stage processes with bounded admission and explicit cleanup."""
import json,os,signal,socket,subprocess,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ResidentPool:
 def __init__(self,log_root):
  self.directory=tempfile.TemporaryDirectory(prefix='multilingua-workers-')
  self.log_root=Path(log_root);self.log_root.mkdir(parents=True,exist_ok=True)
  self.workers={};self.lock=threading.Lock();self.stage_locks={s:threading.Lock() for s in ('asr','translate','tts','lipsync')}
  self.slots={s:threading.BoundedSemaphore(4) for s in self.stage_locks}
 def supports(self,stage,command):
  names={'asr':'asr.py','translate':'translate.py','tts':'tts_parler.py','lipsync':'lipsync_musetalk.py'}
  return stage in names and len(command)>1 and Path(command[1]).name==names[stage]
 def _stop(self,stage):
  item=self.workers.pop(stage,None)
  if item:
   proc,_,log=item
   if proc.poll() is None:
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
     try:os.killpg(proc.pid,signal.SIGKILL)
     except ProcessLookupError:pass
     proc.wait()
   log.close()
 def call(self,stage,command,request,response,log_path,timeout):
  if not self.slots[stage].acquire(blocking=False):raise RuntimeError(f'{stage} worker queue full')
  try:
   with self.stage_locks[stage]:
    with self.lock:
     item=self.workers.get(stage)
     if item and item[0].poll() is not None:self._stop(stage);item=None
     if item is None:
      sock=Path(self.directory.name)/f'{stage}.sock';sock.unlink(missing_ok=True)
      executable=command[0]
      if stage=='lipsync':executable=json.loads(Path(request).read_text())['python']
      log=(self.log_root/f'{stage}-worker.log').open('a')
      proc=subprocess.Popen([executable,str(ROOT/'multilingua/resident_worker.py'),'--stage',stage,'--socket',str(sock)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
      item=(proc,str(sock),log);self.workers[stage]=item
    proc,sock,_=item;deadline=time.monotonic()+timeout
    while not Path(sock).exists():
     if proc.poll() is not None:raise RuntimeError(f'{stage} worker exited; inspect worker log')
     if time.monotonic()>deadline:self._stop(stage);raise TimeoutError(f'{stage} worker startup timed out')
     time.sleep(.05)
    try:
     with socket.socket(socket.AF_UNIX) as client:
      client.settimeout(max(.1,deadline-time.monotonic()));client.connect(sock)
      payload={'argv':command[1:]+['--request',str(request),'--response',str(response)],'log':str(log_path)}
      client.sendall((json.dumps(payload)+'\n').encode());line=client.makefile().readline()
      if not line:raise RuntimeError(f'{stage} worker disconnected')
      result=json.loads(line)
      if not result['ok']:raise RuntimeError(result['error'])
    except (TimeoutError,OSError):
     self._stop(stage);raise
  finally:self.slots[stage].release()
 def evict(self,stage):
  with self.stage_locks[stage]:
   with self.lock:self._stop(stage)
 def cancel_all(self):
  with self.lock:
   for stage in list(self.workers):self._stop(stage)
 def close(self):
  for stage in list(self.workers):self._stop(stage)
  self.directory.cleanup()
