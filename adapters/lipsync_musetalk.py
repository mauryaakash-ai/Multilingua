"""Isolated MuseTalk 1.5 command adapter. Requires official models and environment."""
import argparse,json,re,shutil,subprocess,tempfile,pickle,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--response');a=p.parse_args()
r=json.loads(Path(a.request).read_text());repo=Path(r['repo']).resolve()
# Upstream invokes FFmpeg through shell strings. Stage media under safe paths.
if not re.fullmatch(r'[A-Za-z0-9_./-]+',str(repo)):
    raise ValueError('MuseTalk repository path must not contain whitespace or shell metacharacters')
for file in ('models/musetalkV15/unet.pth','models/musetalkV15/musetalk.json'):
    if not (repo/file).is_file(): raise FileNotFoundError(f'Missing MuseTalk asset: {repo/file}')
with tempfile.TemporaryDirectory(prefix='mlsync_',dir='/tmp') as tmp:
    work=Path(tmp);shutil.copyfile(r['video'],work/'video.mp4');shutil.copyfile(r['audio'],work/'audio.wav')
    # JSON is accepted by OmegaConf's YAML reader.
    cfg=work/'input.yaml';cfg.write_text(json.dumps({'clip':{
        'video_path':str(work/'video.mp4'),'audio_path':str(work/'audio.wav'),'result_name':'dub.mp4'}}))
    command=[r['python'],'-m','scripts.inference','--inference_config',str(cfg),
             '--result_dir',str(work/'results'),'--unet_model_path','models/musetalkV15/unet.pth',
             '--unet_config','models/musetalkV15/musetalk.json','--version','v15',
             '--batch_size',str(r.get('batch_size',2)),'--use_float16','--saved_coord','--ffmpeg_path',str(Path(shutil.which('ffmpeg') or '/usr/bin/ffmpeg').parent)]
    started=time.monotonic()
    subprocess.run(command,cwd=repo,check=True,timeout=r.get('timeout',1800))
    # This pickle is produced by our trusted local worker, never supplied by users.
    coords_path=work/'video.pkl'
    if not coords_path.is_file(): raise RuntimeError('MuseTalk produced no face detection record')
    with coords_path.open('rb') as f: coords=pickle.load(f)
    if not coords or any(tuple(c)==(0,0,0,0) for c in coords):
        raise RuntimeError('Face missing in one or more frames; lip synchronization cannot be certified')
    result=work/'results/v15/dub.mp4'
    if not result.is_file(): raise RuntimeError('MuseTalk produced no output; inspect upstream logs')
    def video_info(path):
        data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-count_frames','-show_entries','stream=duration,nb_read_frames','-of','json',str(path)]))
        return data['streams'][0]
    source_info=video_info(work/'video.mp4'); result_info=video_info(result)
    if abs(float(source_info['duration'])-float(result_info['duration']))>0.1:
        raise RuntimeError('Lip-sync output duration differs from source')
    if abs(int(source_info['nb_read_frames'])-int(result_info['nb_read_frames']))>1:
        raise RuntimeError('Lip-sync output lost frames')
    shutil.copyfile(result,r['output'])
Path(a.response).write_text(json.dumps({'video':r['output'],'face_frames':len(coords),'inference_seconds':time.monotonic()-started}))
