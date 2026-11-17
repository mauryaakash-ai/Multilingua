# Technology and dependency register

| Layer | Technology | Responsibility |
|---|---|---|
| Controller | Python 3.10+, standard library | State machine, validation, JSON adapter requests, locks, timing and artifacts |
| UI | Gradio 6.32, HTML/CSS | Local upload/review/playback, permission controls, progress and downloads |
| Media | FFmpeg + FFprobe, H.264/AAC/PCM/SRT | Decode, normalize, audio fit, cut, mux, concatenate, inspect |
| ASR | faster-whisper / CTranslate2 / Whisper small.en | English transcript and phrase timestamps, CPU INT8 by default |
| Translation | AI4Bharat IndicTrans2 + IndicTransToolkit + Transformers/PyTorch | English–Hindi neural translation |
| Default speech | Indic Parler-TTS + Transformers/PyTorch + SoundFile | Prompt-described generic Hindi voice |
| Alternate speech | IndicF5 + safetensors + Transformers/PyTorch | Hindi speech conditioned on a permitted reference voice |
| Lip sync | MuseTalk 1.5 + upstream vision/audio dependencies | Audio-conditioned mouth-region editing |
| Persistence | Local filesystem, JSON, ZIP | Job state, versioned renders, logs and downloadable deliverables |
| Quality checks | unittest, Ruff, Playwright, GitHub Actions | Contract/media regressions, browser workflows, lint, builds |

**No database, vector database, RAG framework, agent framework or hosted inference API is used.** This is a deterministic local pipeline. Models run in separate subprocess environments to avoid incompatible deep-learning dependencies and release GPU memory between stages.

## Sources, licensing and reproducibility

Project-authored code uses the repository's MIT license. That does not relicense upstream models, datasets, example voices or source video. Follow the linked primary sources and record the exact license files at the chosen revisions before distribution.

| Dependency / asset | Primary source | Required evidence |
|---|---|---|
| Gradio | [Repository](https://github.com/gradio-app/gradio) | Tested UI version and dependency lock |
| FFmpeg | [Official project](https://ffmpeg.org/) | Build configuration, enabled codecs and applicable distribution terms |
| faster-whisper | [Repository](https://github.com/SYSTRAN/faster-whisper) | Package/model revision, model license |
| IndicTrans2 | [Repository](https://github.com/AI4Bharat/IndicTrans2) | Model terms, revision and toolkit versions |
| Indic Parler-TTS | [Model card](https://huggingface.co/ai4bharat/indic-parler-tts) | Model access conditions, weights/code revision and tokenizer dependency |
| IndicF5 | [Model card](https://huggingface.co/ai4bharat/IndicF5) | Weights/code revision and permission for the reference voice |
| MuseTalk | [Repository](https://github.com/TMElyralab/MuseTalk) | Repo commit, v1.5 and auxiliary model terms, environment snapshot |
| Input face/video and voice | Operator's own consent/source record | Capture purpose, permitted editing, class display and redistribution scope |

Model weights and generated face/voice media are not bundled in Git. Historical environment snapshots preserve the original workstation package lists. Current UI/controller dependencies are separately locked and validated. Pin remote model revisions where supported, or use explicit local snapshot directories; do not claim a moving model identifier is reproducible.
