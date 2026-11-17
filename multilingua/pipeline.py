import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from . import media
from .timeline import slots, subtitles
from .config import ROOT, load_config, command


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

class Pipeline:
    def __init__(self, config):
        self.config_path = Path(config).resolve()
        self.config = load_config(self.config_path)
        self.base = self.config_path.parent

    def command(self, stage):
        return command(self.config, stage)

    def adapter(self, stage, job, payload):
        request, response = job / f'{stage}_request.json', job / f'{stage}_response.json'
        write_json(request, payload)
        response.unlink(missing_ok=True)
        cmd = self.command(stage) + ['--request', str(request), '--response', str(response)]
        started = time.monotonic()
        with (job / f'{stage}.log').open('a') as log:
            proc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=self.config.get('timeout_seconds', 1800))
        if proc.returncode or not response.exists():
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
                 'source_language': 'en', 'target_language': 'hi'}
        write_json(job/'job.json', state)
        try:
            t = time.monotonic()
            media.normalize(Path(video).resolve(), job/'source.mp4')
            media.extract_audio(job/'source.mp4', job/'source.wav')
            state['duration'] = media.duration(job/'source.mp4')
            state['timings']['media'] = time.monotonic() - t
            asr, state['timings']['asr'] = self.adapter('asr', job, {
                'audio': str(job/'source.wav'), 'language': 'en'})
            segments = asr['segments']
            if not segments:
                raise ValueError('No speech detected; use a clip with clear English speech')
            list(slots(segments, state['duration']))
            mt, state['timings']['translation'] = self.adapter('translate', job, {
                'texts': [s['text'] for s in segments], 'source': 'eng_Latn', 'target': 'hin_Deva'})
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
        try:
            segments = read_json(review or job/'segments.json')
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
            for i, segment in enumerate(timeline):
                work = job / f'segment_{i:04d}'
                work.mkdir(exist_ok=True)
                seconds = segment['end'] - segment['start']
                media.cut(job/'source.mp4', work/'video.mp4', segment['start'], seconds)
                if segment.get('translation', '').strip():
                    result, elapsed = self.adapter('tts', work, {
                        'text': segment['translation'], 'language': 'hi',
                        'output': str(work/'raw.wav'), **self.config.get('tts', {})})
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
            (job/'output.pending.mp4').unlink(missing_ok=True)
            write_json(job/'job.json', state)
            lock.unlink(missing_ok=True)
        return job/'output.mp4'
