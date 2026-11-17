import json
import math
import os
import shutil
import subprocess
import time
import uuid
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import media
from .languages import language
from .timeline import slots, subtitles

ROOT = Path(__file__).resolve().parents[1]

def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

class Pipeline:
    def __init__(self, config, resident_pool=None):
        self.resident_pool = resident_pool
        self.cancelled=threading.Event()
        self._children=set()
        self._child_lock=threading.Lock()
        self.config_path = Path(config).resolve()
        self.config = read_json(self.config_path)
        self.base = self.config_path.parent

    def cancel(self):
        self.cancelled.set()
        with self._child_lock:
            for proc in self._children:
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        if self.resident_pool:self.resident_pool.cancel_all()

    def command(self, stage):
        command = self.config.get('commands', {}).get(stage)
        if not isinstance(command, list) or not command or not all(isinstance(x,str) for x in command):
            raise ValueError(f'Missing command array for {stage} in configuration')
        return [x.replace('{project}', str(ROOT)) for x in command]

    def adapter(self, stage, job, payload):
        if self.cancelled.is_set():raise RuntimeError('Job cancelled')
        request, response = job / f'{stage}_request.json', job / f'{stage}_response.json'
        write_json(request, payload)
        response.unlink(missing_ok=True)
        cmd = self.command(stage) + ['--request', str(request), '--response', str(response)]
        started = time.monotonic()
        timeout = self.config.get('timeout_seconds', 1800)
        base_command = self.command(stage)
        if self.resident_pool and self.resident_pool.supports(stage, base_command):
            self.resident_pool.call(stage, base_command, request, response, job/f'{stage}.log', timeout)
            returncode = 0
        else:
            if self.resident_pool and stage=='lipsync':self.resident_pool.evict('lipsync')
            with (job / f'{stage}.log').open('a') as log:
                with self._child_lock:
                    if self.cancelled.is_set():raise RuntimeError('Job cancelled')
                    proc = subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    self._children.add(proc)
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait();raise
                finally:
                    with self._child_lock:self._children.discard(proc)
            returncode = proc.returncode
        if returncode or not response.exists():
            raise RuntimeError(f'{stage} failed. Inspect {job / (stage + ".log")}')
        result = read_json(response)
        if not isinstance(result, dict):
            raise ValueError(f'{stage} response must be a JSON object')
        return result, time.monotonic() - started

    def prepare(self, video, runs='runs'):
        # UUID directories avoid collisions between concurrent or repeated runs.
        job = Path(runs).resolve() / uuid.uuid4().hex
        job.mkdir(parents=True)
        state = {'status': 'preparing', 'mode': 'offline', 'timings': {},
                 'source_language': 'en', 'target_language': self.config.get('target_language','hi')}
        write_json(job/'job.json', state)
        try:
            t = time.monotonic()
            media.normalize(Path(video).resolve(), job/'source.mp4')
            media.extract_audio(job/'source.mp4', job/'source.wav')
            state['duration'] = float(next(s for s in media.probe(job/'source.mp4')['streams']
                                           if s['codec_type']=='video')['duration'])
            state['timings']['media'] = time.monotonic() - t
            asr, state['timings']['asr'] = self.adapter('asr', job, {
                'audio': str(job/'source.wav'), 'language': 'en'})
            segments = asr['segments']
            segments = [{**s, 'end': min(s['end'], state['duration'])} for s in segments
                        if s['start'] < state['duration']]
            if not segments:
                write_json(job/'segments.json',[])
                state.update(status='awaiting_review',no_speech=True)
                return job
            list(slots(segments, state['duration']))
            mt, state['timings']['translation'] = self.adapter('translate', job, {
                'texts': [s['text'] for s in segments], 'source': 'eng_Latn', 'target': language(state['target_language'])['translation_target']})
            if len(mt['texts']) != len(segments):
                raise ValueError('Translation count does not match ASR segments')
            for segment, translated in zip(segments, mt['texts']):
                if not isinstance(translated, str) or not translated.strip():
                    raise ValueError('Empty translation returned')
                segment['translation'] = translated
            write_json(job/'segments.json', segments)
            state['status'] = 'awaiting_review'
        except Exception as exc:
            state.update(status='failed', error=str(exc))
            raise
        finally:
            write_json(job/'job.json', state)
        return job

    def render(self, job, review=None, audio_only=False):
        job = Path(job).resolve()
        state = read_json(job/'job.json')
        # Exclusive lock prevents two UI/CLI renders from corrupting the same job.
        lock = job/'.render.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        started = time.monotonic()
        prefetch = None
        try:
            if state.get('no_speech'):
                shutil.copyfile(job/'source.mp4',job/'output.pending.mp4')
                (job/'output.pending.mp4').replace(job/'output.mp4')
                state.update(status='complete',lip_sync=False,output_seconds=state['duration'],render_seconds=0,render_rtf=0)
                write_json(job/'job.json',state)
                return job/'output.mp4'
            segments = read_json(review or job/'segments.json')
            list(slots(segments, state['duration']))
            # Normalized source runs at 25 FPS. Schedule on its frame grid so a
            # trailing sub-frame gap cannot become an audio-only MP4 fragment.
            state['duration'] = float(next(s for s in media.probe(job/'source.mp4')['streams']
                                           if s['codec_type']=='video')['duration'])
            requested = segments
            if self.config.get('use_following_pause', False):
                segments = [{**s, 'end': segments[i+1]['start'] if i+1<len(segments) else state['duration']}
                            for i,s in enumerate(segments)]
            if self.config.get('use_leading_pause', False) and segments:
                segments = [{**segments[0], 'start': 0.0}, *segments[1:]]
            state['timing_policy'] = 'consume_following_pause' if self.config.get('use_following_pause', False) else 'preserve_pauses'
            state['use_leading_pause'] = bool(self.config.get('use_leading_pause', False))
            segments = [{**s, **{k: min(state['duration'], math.floor(s[k]*25+0.5)/25)
                                  for k in ('start','end')}} for s in segments]
            if any(s['end'] <= s['start'] for s in segments):
                raise ValueError('A speech segment is shorter than one video frame; merge it before rendering')
            write_json(job/'requested_segments.json', requested)
            timeline = list(slots(segments, state['duration']))
            if not any(str(s.get('translation','')).strip() for s in segments):
                raise ValueError('No translated speech supplied')
            for s in segments:
                if str(s.get('text','')).strip() and not str(s.get('translation','')).strip():
                    raise ValueError('Every speech segment needs a translation')
            write_json(job/'reviewed_segments.json', segments)
            # Build a candidate separately; a failed rerender preserves the last video.
            (job/'output.pending.mp4').unlink(missing_ok=True)
            state.update(status='rendering', lip_sync=not audio_only)
            state.pop('error', None)
            write_json(job/'job.json', state)
            parts, alignment = [], []
            def synthesize(index):
                segment=timeline[index]
                if not segment.get('translation','').strip():return None
                work=job/f'segment_{index:04d}';work.mkdir(exist_ok=True)
                return self.adapter('tts',work,{
                    'text':segment['translation'],'language':state.get('target_language','hi'),
                    'output':str(work/'raw.wav'),**self.config.get('tts',{})})
            pending_tts=None
            if self.resident_pool and self.config.get('overlap_tts',False):
                prefetch=ThreadPoolExecutor(max_workers=1)
                pending_tts=prefetch.submit(synthesize,0)
            for i, segment in enumerate(timeline):
                if self.cancelled.is_set():raise RuntimeError('Job cancelled')
                synthesized=pending_tts.result() if pending_tts else None
                if prefetch and i+1<len(timeline):
                    pending_tts=prefetch.submit(synthesize,i+1)
                else:pending_tts=None
                work = job / f'segment_{i:04d}'
                work.mkdir(exist_ok=True)
                seconds = segment['end'] - segment['start']
                media.cut(job/'source.mp4', work/'video.mp4', segment['start'], seconds)
                if segment.get('translation', '').strip():
                    result, elapsed = synthesized if synthesized is not None else synthesize(i)
                    if not (work/'raw.wav').is_file():
                        raise RuntimeError('TTS did not create the requested WAV file')
                    fitted = media.fit_audio(work/'raw.wav', work/'audio.wav', seconds,
                                             self.config.get('max_speech_speed', 1.25))
                    alignment.append({'segment':i, **fitted, 'tts_seconds':elapsed})
                    if not audio_only:
                        result, elapsed = self.adapter('lipsync', work, {
                            'video':str(work/'video.mp4'), 'audio':str(work/'audio.wav'),
                            'output':str(work/'lips.mp4'), **self.config.get('lipsync', {})})
                        if not (work/'lips.mp4').is_file():
                            raise RuntimeError('Lip model returned without creating a video')
                        if abs(media.duration(work/'lips.mp4') - seconds) > 0.25:
                            raise RuntimeError('Lip video duration differs from the scheduled slot')
                        alignment[-1]['lipsync_seconds'] = elapsed
                else:
                    media.silence(work/'audio.wav', seconds)
                visual = work/'lips.mp4' if segment.get('translation','').strip() and not audio_only else work/'video.mp4'
                part = job / f'part_{i:04d}.mp4'
                media.mux(visual, work/'audio.wav', part, seconds)
                parts.append(part)
            media.concatenate(parts, job/'output.pending.mp4')
            measured = media.duration(job/'output.pending.mp4')
            if abs(measured-state['duration']) > max(0.25, 0.05*len(parts)):
                raise RuntimeError('Output duration drift exceeds tolerance')
            (job/'subtitles.srt').write_text(subtitles(segments), encoding='utf-8')
            write_json(job/'alignment.json', alignment)
            (job/'output.pending.mp4').replace(job/'output.mp4')
            elapsed = time.monotonic()-started
            state.update(status='complete', output_seconds=measured,
                         render_seconds=elapsed, render_rtf=elapsed/state['duration'])
        except Exception as exc:
            state.update(status='failed', error=str(exc))
            raise
        finally:
            if prefetch:prefetch.shutdown(wait=True,cancel_futures=True)
            (job/'output.pending.mp4').unlink(missing_ok=True)
            write_json(job/'job.json', state)
            lock.unlink(missing_ok=True)
        return job/'output.mp4'
