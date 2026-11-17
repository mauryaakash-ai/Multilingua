> Historical record inherited from the original repository. The referenced model environments, media and logs were not committed and are inaccessible on the current workstation. These observations have not been independently reproduced. See [current validation](VALIDATION.md). Machine-specific presets mentioned below were replaced with portable examples.

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

# Validation record — 14 November 2026

## Executed here
- `python -m unittest discover -s tests -v`: **15 passed**, 3.633 seconds (rerun after media fixes).
- `python -m compileall -q multilingua adapters`: passed.
- `python -m multilingua.cli doctor`: FFmpeg/FFprobe available; NVIDIA driver inaccessible (physical GPU/VRAM unverified); local model config not configured.
- CLI help lists doctor, prepare, render, replay and ui.

The integration suite runs real FFmpeg encoding, decoding, audio stretching/padding, segmentation,
concatenation and subtitle output against synthetic video/audio. Adapter test doubles emit a fixed
Hindi string and a tone; they are confined to tests and are not production models.

Tests cover silence gaps, overlap rejection, finite timestamps, bounds, Unicode subtitles,
queue overload, delay accounting, causal source-window release, output duration, explicit
audio-only mode, no silent fallback after lip failure, render lock, duration overflow, moderate
speech fitting and missing source-audio rejection.

## Not executed here
- faster-whisper, IndicTrans2, IndicF5 and MuseTalk model downloads or inference.
- Gradio installation, UI rendering, browser interaction or accessibility testing.
- Real face editing, Hindi pronunciation/meaning evaluation or speaker identity metrics.
- GPU memory/FPS benchmarks, long-session drift tests, live webcam or network playback.

The package therefore contains a tested controller/media foundation and unvalidated model adapters,
not a certified working GPU integration. No generated sample is represented as neural lip sync.
The supplied environment commands are setup guidance, not a reproducibility lockfile.

## Media corrections verified on 14 November
- Concatenate decoded audio/video with timestamps reset per segment and audio trimmed to each video duration, avoiding accumulated AAC padding.
- Replay uses video stream duration so trailing container audio padding does not create an empty final video chunk.
- Real HDTF source normalized successfully to 30.024 seconds; mono 16 kHz WAV extracted. This validates input media handling, not neural dubbing.

## Real ASR inference — 14 November 2026
Installed faster-whisper 1.2.1, CTranslate2 4.9.0, PyAV 16.0.1 in .venv-speech. Full package snapshot: configs/asr-environment.lock.txt. PyAV 19 was incompatible with faster-whisper's metadata_errors argument and was replaced. Model revision is recorded in runs/hdtf-first/model_revision.json.

Real small.en CPU INT8 inference on the HDTF excerpt produced seven segments. First inference measured 3.082 seconds including model load, excluding model download; not a steady-state benchmark or ASR accuracy score. Final segment timestamps were bounded to decoded audio duration and inference rerun successfully. Transcript: runs/hdtf-first/transcript.txt. Segment bounds passed timeline validation. No human transcript accuracy review performed.

IndicTrans2 and IndicF5 access checks returned GatedRepoError; no local Hugging Face login was found. Translation, speech synthesis and lips remain unexecuted. ASR-only config is configs/asr.local.json; it is deliberately incomplete for full dubbing.

## Translation environment setup
Python 3.10 environment .venv-translation created with torch 2.6.0+cpu, transformers 4.44.2, IndicTransToolkit 1.1.1. Imports and English-to-Hindi text preprocessing passed. Exact installed versions: configs/translation-environment.lock.txt. configs/speech.local.json contains ASR and translation commands only; TTS/lipsync remain unconfigured. Prepared runs/hdtf-first/translate_request.json. Authenticated checks for IndicTrans2 and IndicF5 config files still returned HTTP 403 GatedRepoError. No neural translation ran.

## Approved models and real translation
Both gated model config downloads succeeded after approval. IndicTrans2 revision 2cfd0a20057756d756bf3e53528f492afc52f91a downloaded to models/indictrans2-en-hi. Real CPU translation of seven HDTF transcript segments succeeded; outputs are runs/hdtf-first/segments.json and translation-review.txt. Timings in translation_metrics.json include model loading. These translations require bilingual human review; no adequacy score is claimed. Transformers module cache now defaults to project models/modules. Hindi TTS awaits a permitted reference WAV and its exact transcript; no speech/lip output generated.

## Real Hindi TTS — 16 November 2026
GPU accessible after execution permissions changed: RTX 2000 Ada, 16380 MiB, driver 580.173.02. Earlier NVIDIA-SMI failures were not evidence of absent hardware.

IndicF5 example prompt PAN_F_HAPPY_00001.wav and its official model-card transcript used for a local demonstration. Output voice is the publisher example voice, not the video speaker. Model and code revisions recorded in runs/hdtf-first/tts-provenance.json.

Fixed Transformers 4.44 legacy gamma/beta parameter renaming by constructing from config and loading original safetensors with strict=True. All keys matched. Local model.py also resolves vocabulary from the local checkpoint folder.

Generated runs/hdtf-first/tts-smoke.wav: 3.168 s, mono 24000 Hz. Model load 5.794 s; inference plus output writing 8.084 s; peak CUDA allocation 1476012544 bytes. These are one cold-process test, not sustained latency results. Samples finite, peak 0.8881, RMS 0.1001. No human listening or pronunciation evaluation yet. Full installed packages: configs/tts-environment.lock.txt.

Rerun: `.venv-tts/bin/python adapters/tts_indicf5.py --request runs/hdtf-first/tts_request.json --response runs/hdtf-first/tts_response.json`. Config configs/audio-only.local.json supplies ASR, translation and TTS; lipsync remains unconfigured. Full video dubbing and lip generation have not yet run.

## Real recorded-video audio-only export — 16 November 2026
Completed runs/hdtf-audio-demo/output.mp4 using real ASR, IndicTrans2 and IndicF5 outputs. Original video frames retained; lip_sync=false. Source duration 30.0 s, output 30.043 s. Successful render took 117.914 s (excluding earlier ASR/translation and failed render). Maximum rate adjustment 1.1733. Full output decode passed. Subtitles and reviewed_segments.json exported. Assistant revisions and final-fragment merge logged in revision_history.json; bilingual human evaluation still pending.

Atomic video publication now preserves a previous completed video after failed rerender. Regression suite: 16 passed in 4.395 s.


## Generic male voice and actual lip editing — 2026-11-16
- Indic Parler-TTS access granted and checkpoint downloaded; revision recorded in
  `runs/hdtf-male-demo/provenance.json`. Generic Rohit voice, no source-speaker cloning.
- Six speech segments generated in one model load (6.56 s load, 33.21 s inference total).
  Timing adjustment maximum 1.2052x; no speech truncated. Final PCM is 30 s, 24 kHz,
  finite samples, peak 0.767, no clipped samples.
- MuseTalk v1.5 processed all 750 source frames in 257.04 s. Final video and audio
  stream durations are both 30.000 s; output has 750 frames. Face detection succeeded
  for every frame. Source/output samples at 2, 14, 27 s show mouth edits without obvious
  gross compositing errors. This is a sampled visual check, not a perceptual lip-sync score.
- Output: `runs/hdtf-male-demo/lipsynced.mp4`. Comparison: `audio-only.mp4`.
  Human listening, translation review and temporal lip-sync review remain pending.
  The source excerpt starts and ends mid-sentence.
- Fixed MuseTalk adapter to retain coordinates using `--saved_coord`; added output
  duration and frame-count checks. Environment locks capture sentencepiece 0.2.0 and
  compatible protobuf for the generic TTS tokenizer.
- All 16 unit/integration tests pass (4.193 s). Gradio 6.31 local UI opened successfully
  with `configs/generic-voice.local.json`; bound to localhost, no public deployment.
