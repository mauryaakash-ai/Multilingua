"""Reviewable offline orchestration with isolated, versioned render artifacts."""
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import uuid
import zipfile

from . import media
from .config import ROOT, command, load_config
from .timeline import frame_slots, subtitles, validate_segments


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Pipeline:
    def __init__(self, config, progress=None):
        self.config_path = Path(config).resolve()
        self.config = load_config(self.config_path)
        self.progress = progress or (lambda fraction, message: None)

    def command(self, stage):
        return command(self.config, stage)

    def adapter(self, stage, job, payload):
        request, response = job / f'{stage}_request.json', job / f'{stage}_response.json'
        write_json(request, payload)
        response.unlink(missing_ok=True)
        # A response alone cannot validate a stale artifact from an earlier invocation.
        if stage in ('tts', 'lipsync'):
            Path(payload['output']).unlink(missing_ok=True)
        cmd = self.command(stage) + ['--request', str(request), '--response', str(response)]
        started = time.monotonic()
        log_path = job / f'{stage}.log'
        with log_path.open('a', encoding='utf-8') as log:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=os.name == 'posix')
            try:
                proc.wait(timeout=self.config.get('timeout_seconds', 1800))
            except BaseException as exc:
                # MuseTalk launches another process; kill the entire group on POSIX.
                if os.name == 'posix':
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()
                proc.wait()
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise RuntimeError(f'{stage} timed out. Inspect {log_path}') from exc
                raise
        if proc.returncode or not response.exists():
            raise RuntimeError(f'{stage} failed. Inspect {log_path}')
        result = read_json(response)
        if not isinstance(result, dict):
            raise ValueError(f'{stage} response must be a JSON object')
        return result, time.monotonic() - started

    def prepare(self, video, runs='runs'):
        job = Path(runs).resolve() / uuid.uuid4().hex
        job.mkdir(parents=True)
        state = {'status': 'preparing', 'mode': 'offline', 'timings': {},
                 'source_language': 'en', 'target_language': 'hi',
                 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        write_json(job / 'job.json', state)
        try:
            self.progress(0.05, 'Normalizing video and extracting audio')
            t = time.monotonic()
            media.normalize(Path(video).resolve(), job / 'source.mp4')
            media.extract_audio(job / 'source.mp4', job / 'source.wav')
            state['duration'] = media.video_duration(job / 'source.mp4')
            state['timings']['media'] = time.monotonic() - t
            self.progress(0.25, 'Recognizing English speech')
            asr, state['timings']['asr'] = self.adapter('asr', job, {
                'audio': str(job / 'source.wav'), 'language': 'en'})
            segments = validate_segments(asr.get('segments'), state['duration'])
            self.progress(0.6, 'Translating speech into Hindi')
            mt, state['timings']['translation'] = self.adapter('translate', job, {
                'texts': [s['text'] for s in segments], 'source': 'eng_Latn', 'target': 'hin_Deva'})
            texts = mt.get('texts')
            if not isinstance(texts, list) or len(texts) != len(segments):
                raise ValueError('Translation response must contain one text per ASR segment')
            for segment, translated in zip(segments, texts):
                segment['translation'] = translated
            validate_segments(segments, state['duration'], translated=True)
            write_json(job / 'segments.json', segments)
            state['status'] = 'awaiting_review'
            self.progress(1, 'Ready for bilingual review')
        except BaseException as exc:
            state.update(status='failed', error=str(exc) or type(exc).__name__)
            raise
        finally:
            write_json(job / 'job.json', state)
        return job

    def render(self, job, review=None, audio_only=False):
        job = Path(job).resolve()
        lock = job / '.render.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        state = None
        started = time.monotonic()
        attempt = job / 'renders' / uuid.uuid4().hex
        try:
            state = read_json(job / 'job.json')
            segments = validate_segments(read_json(review or job / 'segments.json'),
                                         state['duration'], translated=True)
            timeline = list(frame_slots(segments, state['duration']))
            attempt.mkdir(parents=True)
            write_json(attempt / 'reviewed_segments.json', segments)
            state.update(status='rendering', active_render=str(attempt.relative_to(job)))
            state.pop('error', None)
            write_json(job / 'job.json', state)
            parts, alignment = [], []
            for i, segment in enumerate(timeline):
                self.progress(i / len(timeline), f'Rendering interval {i + 1} of {len(timeline)}')
                work = attempt / f'segment_{i:04d}'
                work.mkdir()
                seconds = segment['end'] - segment['start']
                media.cut(job / 'source.mp4', work / 'video.mp4', segment['start'], seconds)
                speech = bool(segment.get('translation', '').strip())
                if speech:
                    _, elapsed = self.adapter('tts', work, {
                        **self.config.get('tts', {}), 'text': segment['translation'],
                        'language': 'hi', 'output': str(work / 'raw.wav')})
                    if not (work / 'raw.wav').is_file():
                        raise RuntimeError('TTS did not create the requested WAV file')
                    fitted = media.fit_audio(work / 'raw.wav', work / 'audio.wav', seconds,
                                             self.config.get('max_speech_speed', 1.25))
                    alignment.append({'segment': i, 'start': segment['start'], 'end': segment['end'],
                                      **fitted, 'tts_seconds': elapsed})
                    if not audio_only:
                        _, elapsed = self.adapter('lipsync', work, {
                            **self.config.get('lipsync', {}), 'video': str(work / 'video.mp4'),
                            'audio': str(work / 'audio.wav'), 'output': str(work / 'lips.mp4')})
                        if not (work / 'lips.mp4').is_file():
                            raise RuntimeError('Lip model returned without creating a video')
                        if abs(media.video_duration(work / 'lips.mp4') - seconds) > 0.1:
                            raise RuntimeError('Lip video duration differs from the scheduled slot')
                        alignment[-1]['lipsync_seconds'] = elapsed
                else:
                    media.silence(work / 'audio.wav', seconds)
                visual = work / ('lips.mp4' if speech and not audio_only else 'video.mp4')
                part = attempt / f'part_{i:04d}.mp4'
                media.mux(visual, work / 'audio.wav', part, seconds)
                parts.append(part)
            self.progress(0.95, 'Checking timing and packaging downloads')
            media.concatenate(parts, attempt / 'output.mp4')
            measured = media.duration(attempt / 'output.mp4')
            if abs(measured - state['duration']) > 0.12:
                raise RuntimeError('Output duration drift exceeds 120 ms')
            (attempt / 'subtitles.srt').write_text(subtitles(segments), encoding='utf-8')
            write_json(attempt / 'alignment.json', alignment)
            elapsed = time.monotonic() - started
            report = {'ai_dubbed': True, 'lip_sync': not audio_only,
                      'source_seconds': state['duration'], 'output_seconds': measured,
                      'render_seconds': elapsed, 'render_rtf': elapsed / state['duration'],
                      'python': platform.python_version(),
                      'source_sha256': sha256(job / 'source.mp4'),
                      'output_sha256': sha256(attempt / 'output.mp4'),
                      'config_sha256': sha256(self.config_path),
                      'human_quality_review': 'pending',
                      'note': 'AI-dubbed Hindi. Review meaning, voice and visual quality before sharing. '
                              'Model revision/license records are supplied separately by the operator.'}
            write_json(attempt / 'provenance.json', report)
            (attempt / 'AI-DUBBED.txt').write_text(report['note'], encoding='utf-8')
            artifacts = ['output.mp4', 'subtitles.srt', 'reviewed_segments.json',
                         'alignment.json', 'provenance.json', 'AI-DUBBED.txt']
            with zipfile.ZipFile(attempt / 'delivery.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
                for name in artifacts:
                    archive.write(attempt / name, name)
            # All aliases resolve through one atomic pointer, keeping video and metadata together.
            pointer = job / '.current.pending'
            pointer.unlink(missing_ok=True)
            pointer.symlink_to(attempt.relative_to(job), target_is_directory=True)
            pointer.replace(job / 'current')
            for name in [*artifacts, 'delivery.zip']:
                alias = job / name
                if not alias.is_symlink():
                    pending = job / (name + '.pending')
                    pending.unlink(missing_ok=True)
                    pending.symlink_to(Path('current') / name)
                    pending.replace(alias)
            state.update(status='complete', lip_sync=not audio_only,
                         published_render=str(attempt.relative_to(job)),
                         output_seconds=measured, render_seconds=elapsed,
                         render_rtf=elapsed / state['duration'])
            self.progress(1, 'AI-dubbed video ready for quality review')
        except BaseException as exc:
            if state is not None:
                state.update(status='failed', error=str(exc) or type(exc).__name__)
            raise
        finally:
            try:
                if state is not None:
                    state.pop('active_render', None)
                    write_json(job / 'job.json', state)
            finally:
                lock.unlink(missing_ok=True)
        return job / 'output.mp4'
