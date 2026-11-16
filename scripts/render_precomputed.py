"""Fit previously generated speech and export a continuous audio-only comparison."""
import argparse
import json
from pathlib import Path
import sys
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from multilingua import media
from multilingua.timeline import slots, subtitles

p=argparse.ArgumentParser()
p.add_argument('job')
p.add_argument('--source',required=True)
a=p.parse_args()
job=Path(a.job).resolve(); source=Path(a.source).resolve()
segments=json.loads((job/'segments.json').read_text())
video=next(s for s in media.probe(source)['streams'] if s['codec_type']=='video')
total=float(video['duration']); timeline=list(slots(segments,total))
alignment=[];speech_index=0; files=[]
for i,s in enumerate(timeline):
    seconds=s['end']-s['start']; fitted=job/f'fitted_{i:04d}.wav'
    if s.get('translation','').strip():
        raw=job/f'segment_{speech_index:04d}'/'raw.wav';speech_index+=1
        stats=media.fit_audio(raw,fitted,seconds,1.25)
        alignment.append({'start':s['start'],'end':s['end'],**stats})
    else:media.silence(fitted,seconds)
    files.append(fitted)
with wave.open(str(job/'dubbed.wav'),'wb') as out:
    out.setnchannels(1);out.setsampwidth(2);out.setframerate(24000)
    for f in files:
        with wave.open(str(f),'rb') as inp:
            if (inp.getnchannels(),inp.getsampwidth(),inp.getframerate())!=(1,2,24000):
                raise ValueError('Unexpected fitted WAV format')
            out.writeframes(inp.readframes(inp.getnframes()))
candidate=job/'audio-only.pending.mp4'
media.mux(source,job/'dubbed.wav',candidate,total)
if abs(media.duration(candidate)-total)>0.1:raise ValueError('Output duration drift')
candidate.replace(job/'audio-only.mp4')
(job/'subtitles.srt').write_text(subtitles(segments),encoding='utf-8')
(job/'alignment.json').write_text(json.dumps(alignment,indent=2))
print(job/'audio-only.mp4')
