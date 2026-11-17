#!/usr/bin/env bash
# Install the standalone English-to-Hindi audio-only setup without gated weights.
set -euo pipefail
cd "$(dirname "$0")/.."

uv venv --allow-existing --python 3.11 .venv-speech
uv pip install --python .venv-speech/bin/python \
  'faster-whisper==1.2.1' 'ctranslate2==4.9.0' 'av==16.0.1' 'numpy<2.5'

uv venv --allow-existing --python 3.11 .venv-open-models
uv pip install --python .venv-open-models/bin/python \
  --index-url https://download.pytorch.org/whl/cpu 'torch==2.6.0+cpu'
uv pip install --python .venv-open-models/bin/python \
  'transformers==4.57.6' 'huggingface-hub<1' 'numpy<2.5' sentencepiece sacremoses

.venv-open-models/bin/python - <<'PY'
from concurrent.futures import ThreadPoolExecutor

from huggingface_hub import snapshot_download

models = (
    ("Systran/faster-whisper-small.en", "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
     "models/whisper-small-en", ["*.json", "model.bin", "vocabulary.txt"]),
    ("Helsinki-NLP/opus-mt-en-hi", "75d7f7c9232b2891c7d65fe4ef635616c72be867",
     "models/opus-en-hi", ["*.json", "*.spm", "pytorch_model.bin"]),
    ("facebook/mms-tts-hin", "1d83b223ec78e30b944f7d96bd117eb3d7023303",
     "models/mms-tts-hin", ["*.json", "model.safetensors"]),
)

def download(spec):
    repo, revision, folder, files = spec
    return snapshot_download(
        repo, revision=revision, local_dir=folder, allow_patterns=files, max_workers=3
    )

with ThreadPoolExecutor(max_workers=3) as pool:
    for folder in pool.map(download, models):
        print(f"Ready: {folder}")
PY

printf 'Start the studio with: .venv/bin/python -m multilingua.cli --config configs/open-models.example.json ui\n'
