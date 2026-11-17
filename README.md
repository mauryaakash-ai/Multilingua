# Multilingua • English–Hindi Lip-Synced Video Dubbing

A local research implementation with a reviewable offline pipeline, model adapters,
FFmpeg media handling, optional UI, tests and a concrete plan to reach live streaming.

**Status:** orchestration and synthetic media tests can run without a GPU. Neural model integration
requires official downloads and verification on your machine. Live webcam translation is not implemented.
See docs/COMPLETION_PLAN.md for completion gates and docs/VALIDATION.md for actual test results.

## Quick start: infrastructure only (Ubuntu)
```bash
sudo apt update
sudo apt install ffmpeg python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
cp configs/local.example.json configs/local.json
python -m multilingua.cli doctor
```
The synthetic integration tests create a solid-color video and test tones in temporary directories.
They do NOT validate translation, TTS or lips. Nothing silently substitutes a fake model in normal use.

## Model environments
Use separate Conda environments to avoid upstream dependency conflicts. Paths below are examples;
use `which python` inside each environment and paste that absolute path into local.json.
Do not assume your Conda installation is under miniconda3. Source code requires Python >=3.10.

### ASR and translation
```bash
conda create -n mlspeech python=3.10 -y
conda activate mlspeech
pip install faster-whisper transformers sentencepiece sacremoses torch
pip install indictranstoolkit
```
Follow https://github.com/AI4Bharat/IndicTrans2 for the model's supported dependency versions and gated
access if requested. The adapter uses IndicProcessor with the official Hugging Face interface.
CPU defaults reduce competition with the visual model. CUDA can be selected in command arguments.
These are setup commands, not a verified package lock. After a successful inference, save `pip freeze`.

### Hindi TTS
```bash
conda create -n mltts python=3.10 -y
conda activate mltts
pip install git+https://github.com/ai4bharat/IndicF5.git
```
Follow https://huggingface.co/ai4bharat/IndicF5, accept model access terms if required,
and configure a short consented reference WAV plus its exact spoken transcript.
Model downloads may require `hf auth login` (install huggingface_hub CLI if unavailable).
The current model card recommends Indic-Speak as a successor; IndicF5 is used here for its documented
adapter interface. Benchmark successors before replacing it; this is not a claim that IndicF5 is best.

### MuseTalk
Clone https://github.com/TMElyralab/MuseTalk into a path without spaces (e.g. ~/MuseTalk).
Follow that repository's current installation and weight-download instructions in its own environment.
Download ALL documented auxiliary models, not just the UNet. Check normal inference on an official
example before connecting this project. Copy the repository path and its Python executable into config.
Expected 1.5 UNet assets: models/musetalkV15/unet.pth and models/musetalkV15/musetalk.json.
The adapter uses official scripts.inference, version v15, FP16, batch size 2. Reduce batch size in
adapters/lipsync_musetalk.py if needed. Record `git rev-parse HEAD` after validating the interface.

## Configure
Edit configs/local.json:
- commands.asr / commands.translate: absolute mlspeech Python executable.
- commands.tts: absolute mltts Python executable.
- commands.lipsync: controller Python executable; it launches MuseTalk's own Python.
- tts.reference_audio: absolute path to consented reference WAV.
- tts.reference_text: exact transcript of that reference WAV.
- lipsync.repo and lipsync.python: official checkout and environment.
The `{project}` placeholder resolves automatically to this extracted project's root.
Model commands are trusted local configuration; do not expose config editing to untrusted users.

## Run a real video
```bash
source .venv/bin/activate
python -m multilingua.cli --config configs/local.json prepare /absolute/path/input.mp4
```
The command prints a job directory. Open `runs/JOB_ID/segments.json`, correct Hindi translations,
and retain numeric start/end timestamps. Every speech segment must have a nonempty translation.
```bash
python -m multilingua.cli --config configs/local.json render runs/JOB_ID --audio-only
python -m multilingua.cli --config configs/local.json render runs/JOB_ID
```
Audio-only is a useful explicit comparison, not a successful lip-sync result.
If speech is more than 25% too long for a slot, shorten the translation and rerun.
The controller never silently cuts off translated words. Rendering recomputes segments; it is not a
checkpoint resume mechanism. A successful rerender replaces the video atomically; a failed rerender preserves the previous completed video. Copy desired comparisons before a successful rerender.

Outputs: output.mp4, subtitles.srt, reviewed_segments.json, alignment.json, job.json and logs.
Silent source intervals become silence; music/background ambience is not preserved in this release.
Maximum source duration: 10 minutes. Start with a 20–30-second clear single-speaker clip.

## Optional review UI
```bash
source .venv/bin/activate
pip install -e '.[ui]'
python -m multilingua.cli --config configs/local.json ui
```
Open the printed localhost address. Upload, transcribe/translate, review JSON, confirm permission,
then render. UI stays local with no public share link. It is not a production upload service.
Run the UI on the GPU machine and use an SSH tunnel if you want to access it from your laptop.

## Debugging
- Missing weights/access: inspect the named adapter log and test that environment independently.
- No face / empty MuseTalk output: choose a clear frontal video and inspect lipsync.log.
- Speech too long: edit the translation; do not increase the speed cap arbitrarily.
- CUDA out of memory: keep speech models on CPU, reduce lip batch size, shorten the clip.
- Failed job: read job.json and logs; rerun prepare if transcription failed, render if synthesis failed.
- Stale .render.lock after a killed process: confirm no render is active before deleting that lock.
- Source has no audio / invalid timeline: fix the input; the pipeline rejects these conditions.

## Research and live completion
Read docs/COMPLETION_PLAN.md. Current subprocess-per-phrase loading is intentionally an offline
baseline. To claim live performance, implement persistent workers, causal audio segmentation,
WebRTC capture/output and clocked bounded buffers; benchmark on target hardware.
The included streaming.simulate utility only evaluates a queue schedule from measured processing
costs. It does not capture a webcam or perform streaming inference.

## License and reproducibility
Project-authored code is MIT (LICENSE). Third-party models, code and datasets keep their own terms.
No model weights are bundled. Voice-cloning configurations require permission for the reference voice; generic Parler presets do not use a reference recording.
Record OS, GPU, driver, FFmpeg version, model revisions and frozen packages with each experiment.

## Causal replay benchmark (implemented, not webcam streaming)
```bash
python -m multilingua.cli --config configs/local.json replay input.mp4 --chunk-seconds 6 --max-waiting 2
```
Chunks are released only after their source-time window closes. One worker processes chunks using
the model adapters; bounded queue overload stops the run rather than hiding growing delay. Each
chunk's output path and queue/compute/ready timings are saved in chunks.json. replay.json reports
ready-delay percentiles; these are not receiver playback latency. No continuous player is implemented.
This benchmark uses automatic translations (no interactive review) and should use consented test clips.
Phrase splitting at fixed chunk boundaries and repeated model loading intentionally expose baseline
limitations. All-silence chunks currently fail ASR rather than passing through; add VAD-aware handling
before production use. The scheduler simulator remains available for fast cost-only experiments.


## Generic Hindi voice demo
Use `configs/generic-voice.local.json` for Indic Parler-TTS (Rohit) and MuseTalk 1.5.
This preset uses a generic formal male voice and needs no reference WAV. Other speakers
may need a different voice description. Models are local and require their separate environments.

```bash
python -m multilingua.cli --config configs/generic-voice.local.json ui
```
The interface binds to `127.0.0.1:7860` by default. This is local testing, not a public deployment.
Gradio 6 is the tested UI major version. GPU subprocesses need access to the NVIDIA driver.
The reviewed demo assets and measurements are in `runs/hdtf-male-demo/`.
`audio-only.mp4` retains original lips; `lipsynced.mp4` is the MuseTalk output when rendering succeeds.
`subtitles.srt`, `alignment.json`, and `provenance.json` record text, timing, and model sources.
Human listening and temporal lip-quality review remain necessary before treating this as a benchmark.


## Evaluation and experimental webcam service
See `docs/EVALUATION_REPORT.md` for measured results and limitations. Reproducible metric entry points:
- `scripts/evaluate_syncnet.py`: official face tracking plus SyncNet scores, offsets and provenance.
- `scripts/evaluate_hindi_speech.py`: Hindi recognition consistency (WER/CER), not human MOS.
- `scripts/evaluate_text.py`: reference-based WER/CER and chrF++; missing references stay unscored.

`python scripts/serve_local.py` starts an authenticated **localhost-only** test service on port 7861.
Credentials are generated into `.runtime/local-login.json` (private, gitignored); open in a browser
that supports HTTP Basic authentication. Some embedded browsers do not support its login prompt.
Camera and microphone activate only when the user clicks Start and grants browser permission.
The experimental frontend sends complete six-second recordings, with a bounded queue and explicit
failure/overload messages. It is not continuous WebRTC or validated real-time dubbing. Queued jobs
continue after capture stops. Automatic timing may use leading/following silence, recorded in job
metadata; it never raises the 1.25x speed cap. Overlong translations still need manual review.

`deploy/` contains a single-operator authenticated API deployment candidate with systemd and Caddy
configuration. No public host is provisioned. See its README for remaining release requirements.
