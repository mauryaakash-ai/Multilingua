"""Local XTTS Spanish speech using a bundled generic speaker, not user voice cloning."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--response', required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text())
    if request.get('language') != 'es':
        raise ValueError('This adapter supports Spanish only')
    if request.get('reference_audio') or request.get('speaker_wav'):
        raise ValueError('Use a bundled generic speaker in this adapter')
    folder = Path(request['model'])
    for name in ('config.json', 'model.pth', 'vocab.json', 'speakers_xtts.pth'):
        if not (folder / name).is_file():
            raise ValueError(f'Missing local XTTS file: {folder / name}')
    import numpy as np
    import soundfile as sf
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import Xtts
    config = XttsConfig()
    config.load_json(str(folder / 'config.json'))
    model = Xtts.init_from_config(config)
    model.load_checkpoint(config, checkpoint_dir=str(folder), eval=True)
    model.to(request.get('device', 'cuda'))
    speaker = request.get('speaker', 'Ana Florence')
    if speaker not in model.speaker_manager.speakers:
        raise ValueError(f'Bundled speaker unavailable: {speaker}')
    conditioning = model.speaker_manager.speakers[speaker]
    result = model.inference(request['text'], 'es', conditioning['gpt_cond_latent'], conditioning['speaker_embedding'])
    audio = np.asarray(result['wav'], dtype=np.float32)
    if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
        raise ValueError('XTTS returned invalid audio')
    output = Path(request['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    rate = config.audio.output_sample_rate
    sf.write(output, audio, rate)
    Path(args.response).write_text(json.dumps({'audio': str(output), 'audio_seconds': len(audio)/rate, 'speaker': speaker}))


if __name__ == '__main__':
    main()
