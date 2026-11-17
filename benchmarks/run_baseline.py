import subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'runs/profiling/baseline'
workers={'asr':root/'.venv-speech/bin/python','translation':root/'.venv-translation/bin/python','tts':root/'.venv-voice/bin/python','musetalk':Path('/home/akash/MuseTalk/.venv/bin/python'),'ffmpeg':Path(sys.executable)}
for stage,python in workers.items():
 with (out/f'{stage}.log').open('w') as log:
  result=subprocess.run([str(python),str(root/'benchmarks/profile_stage.py'),'--stage',stage,'--fixture',str(out/'fixture.json'),'--output',str(out/f'{stage}.json')],cwd=root,stdout=log,stderr=subprocess.STDOUT)
 print(stage,result.returncode,flush=True)
 if result.returncode:sys.exit(result.returncode)
