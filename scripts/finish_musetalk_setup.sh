#!/usr/bin/env bash
set -euo pipefail
repo="${1:?Usage: finish_musetalk_setup.sh /absolute/path/to/MuseTalk}"
project="$(cd "$(dirname "$0")/.." && pwd)"
py="$repo/.venv/bin/python"
# Run after the initial PyTorch installation has completed.
"$py" -c 'import torch, torchvision, torchaudio; assert torch.cuda.is_available(); print(torch.__version__)'
"$py" -m pip install 'diffusers==0.30.2' 'accelerate==0.28.0' 'numpy==1.23.5' 'opencv-python==4.9.0.80' 'soundfile==0.12.1' 'transformers==4.39.2' 'huggingface_hub==0.30.2' 'librosa==0.11.0' 'einops==0.8.1' omegaconf ffmpeg-python 'imageio[ffmpeg]' 'moviepy<2' scipy matplotlib tqdm
"$py" -m pip install 'mmengine>=0.8,<1' 'mmcv==2.0.1' -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0/index.html
"$py" -m pip install wheel 'chumpy==0.70' --no-build-isolation
"$py" -m pip install 'mmdet==3.1.0' 'mmpose==1.1.0'
cd "$repo"
"$py" -m scripts.inference --help
"$py" -m pip freeze > "$project/configs/lipsync-environment.lock.txt"
