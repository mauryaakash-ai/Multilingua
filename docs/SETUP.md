# Setup and operation

## Supported workstation

Linux, Python 3.10+ for the controller (tested here on 3.11), FFmpeg/FFprobe with H.264/AAC, and a browser. Model environments have their own upstream Python/CUDA constraints: use Python 3.10 for the historical model package snapshots. A CUDA GPU is normally needed for practical speech/lip generation; CPU-only media tests do not need one. A 16 GB card is a starting point, not a universal memory guarantee.

## 1. Controller and UI

```bash
git clone https://github.com/mauryaakash-ai/Multilingua.git
cd Multilingua
sudo apt update
sudo apt install ffmpeg python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[ui]'
python -m unittest discover -s tests -v
python -m multilingua.cli ui
```

The studio opens at http://127.0.0.1:7860 even before model setup; it shows a setup notice. This does not mean neural inference is available. `--port 7861` selects another port. No public share link is created. Keep the browser on the GPU workstation or use an authenticated SSH tunnel; don't change the bind address to expose this prototype.

If you cannot install system packages, use an existing Conda installation:

```bash
conda create -n mlmedia -c conda-forge ffmpeg -y
conda activate mlmedia
# Then activate the controller venv, preserving FFmpeg on PATH.
source .venv/bin/activate
```

The exact controller/UI dependency set tested here is `configs/ui-requirements.lock.txt` (Python 3.11/Linux). Install it before `pip install -e .` for reproduction. Historical `*-environment.lock.txt` snapshots for heavy models came from a different workstation; they are evidence, not proof that every machine can install those binaries.

## 2. Configure isolated model environments

```bash
cp configs/local.example.json configs/local.json
```

The default example uses generic Hindi Parler speech and requires no reference voice. It expects `.venv-speech`, `.venv-translation`, `.venv-voice` under the checkout; create them with compatible Python versions or replace command paths with the actual environment executables. Every command is a JSON argument array. `{project}` resolves to the source checkout, `{python}` to the active controller interpreter; `~` and environment variables such as `${HOME}` expand in string values. Run commands from the repository root. Local configuration is ignored by Git.

**ASR:** install the [official faster-whisper](https://github.com/SYSTRAN/faster-whisper) package in the speech environment. The example uses `small.en`, CPU INT8. Freeze the model revision or use an explicit downloaded snapshot directory. Historical versions are in `configs/asr-environment.lock.txt`.

**Translation:** follow [IndicTrans2's official instructions](https://github.com/AI4Bharat/IndicTrans2), including `IndicTransToolkit`, tokenizer dependencies, model access and compatible Transformers. Use a separate translation environment; the existing snapshot records a Transformers 4.44 stack. Default model: `ai4bharat/indictrans2-en-indic-dist-200M`. Set `--revision COMMIT` for remote loads or `--model /absolute/snapshot/path`.

**Generic speech:** follow the [Indic Parler-TTS model card](https://huggingface.co/ai4bharat/indic-parler-tts) and install the official [Parler-TTS package](https://github.com/huggingface/parler-tts) into the voice environment. The repository includes a historical package snapshot with an upstream Git revision. Accept any gated terms using your own Hugging Face account. `tts.model` may be a model identifier or local snapshot; `tts.revision` pins remote weights. The description tokenizer is a separate model dependency and must also be cached for disconnected use. The generic voice is not the source speaker's cloned identity.

**Optional reference speech:** copy `configs/reference-voice.example.json` instead. Follow [IndicF5](https://huggingface.co/ai4bharat/IndicF5) installation, and provide a reference WAV you have permission to use plus its exact spoken transcript. The adapter loads safetensors strictly to avoid the legacy gamma/beta key-remapping issue documented by the original implementation. Verify compatibility against the chosen upstream revision. Do not assume a model-card example voice grants every downstream use.

**Lip sync:** clone [MuseTalk](https://github.com/TMElyralab/MuseTalk) to a path without spaces, such as `~/MuseTalk`, and follow its official installation and full auxiliary-weight download instructions. Its Python environment is separate from the controller. Validate an official example first. Set `lipsync.repo` and `lipsync.python`. The adapter expects v1.5 UNet assets, `scripts.inference`, saved face coordinates and a generated MP4. `scripts/finish_musetalk_setup.sh /absolute/MuseTalk` is a historical CUDA 11.8/PyTorch 2.0 helper, not a generic driver installer; inspect it and prefer upstream guidance for a different stack.

Upstream model cards mention newer successors. Keep the original adapters for project continuity; benchmark replacements after the presentation rather than switching without a rehearsal.

Never paste tokens into JSON configs, shell scripts committed to Git or adapter requests. Authenticate through the official model-host CLI in the model environment. Review `trust_remote_code` sources before allowing them to execute.

## 3. Preflight

```bash
python -m multilingua.cli --config configs/local.json doctor
# For a deliberately audio-only setup:
python -m multilingua.cli --config configs/local.json doctor --audio-only
nvidia-smi
```

Doctor exits 1 for missing required dependencies/configuration and 0 when local path checks pass. It does not certify model imports, gated access, all auxiliary assets or quality. Finish with a real short-clip rehearsal. Record model revisions, package freezes and hardware in your run log.

## 4. UI workflow

Upload → confirm permission → transcribe/translate → edit Hindi → confirm review → select mode → generate → watch/listen → download. Source text/timing are locked in the browser and validated server-side. Changing the source clears previous results and permission/review checks. Editing Hindi resets review approval. Progress describes the actual active stage, not estimated completion time.

If ASR itself is incorrect, use the CLI to correct source/segment definitions and re-run translation via the adapter contract before rendering; the simple UI is intentionally focused on translation review. See `adapters/PROTOCOL.md`.

## 5. CLI workflow and outputs

```bash
python -m multilingua.cli --config configs/local.json prepare /absolute/input.mp4
# Review runs/JOB_ID/segments.json; translations must be nonempty strings.
python -m multilingua.cli --config configs/local.json render runs/JOB_ID --audio-only
python -m multilingua.cli --config configs/local.json render runs/JOB_ID
```

Each success remains in `runs/JOB_ID/renders/RENDER_ID/`. `current` is an atomic symlink to the latest success. Top-level `output.mp4`, `subtitles.srt`, `reviewed_segments.json`, `alignment.json`, `provenance.json`, `AI-DUBBED.txt` and `delivery.zip` resolve through it. Keep separate render directories for comparisons. A later failed render retains the previous successful bundle. The UI returns immutable paths for its downloads.

`job.json` records current status, prepare timings, render duration/RTF and last published render. Per-phrase directories include requests, responses and logs. No checkpoint reuse is implied: rerendering regenerates speech/lips. Disk use grows with attempts; delete entire jobs only when no render is active. Do not edit the published symlink targets; use a new review and render.

The archive is marked AI-dubbed and includes text/timing evidence. Its disclosure is **not** burned into video pixels. Include a visible AI-dubbed label when presenting or sharing the MP4 by itself.

## Troubleshooting

| Symptom | Action |
|---|---|
| Config/executable missing | Use the system-check details; replace example paths with `which python` from the appropriate environment |
| HTTP 401/403 / gated download | Accept model terms and authenticate in that environment; do not bypass access checks |
| Translation overflow | Split a long source phrase using valid timestamps, or reduce translation length after meaning review |
| Speech too long for slot | Shorten Hindi, preserving meaning; do not raise the 1.25× cap |
| No face / lip frame mismatch | Use a frontal clip with no cuts/occlusion and inspect the named lip log |
| CUDA OOM | Keep ASR/MT on CPU, reduce MuseTalk batch size, close other GPU processes, shorten clip |
| Adapter timeout | Inspect its log; timeout terminates the process group on Linux. Fix setup or shorten input before retrying |
| `.render.lock` remains after host kill | Confirm no process is rendering this job, then remove only that stale lock |
| No speech or silent replay chunk | Use clear speech; silent-window pass-through is not implemented in causal replay |
| Incomplete metadata after host crash | Inspect `current` and its immutable bundle; `job.json` can lag the atomic publication pointer |

## Developer checks

```bash
pip install -e '.[ui,dev]'
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python tests/browser_smoke.py
python -m build
```

Browser checks use installed Google Chrome or Playwright Chromium (`playwright install chromium` if needed). Test fixtures are explicitly synthetic and confined to tests. CI runs media, contract, UI-build and packaging checks; browser smoke is also run in CI with Chromium. The source checkout is required for adapter scripts/configuration; the wheel packages the controller, not model assets or external model environments.
