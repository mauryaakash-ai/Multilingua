# Adapter contract
Each command is an argument array, followed by `--request FILE --response FILE`.
Read request JSON; write response JSON only on success; exit nonzero on failure.
Do not write credentials to logs. Config is trusted local code execution configuration,
never accept it from a network user. Each model runs in its own subprocess so package
conflicts are isolated and GPU memory is released when the process ends.

- ASR input: audio path and language. Output: segments with start/end seconds and text.
- Translation input: texts array, source and target language codes. Output: texts array of equal length.
- TTS input: text, language, output WAV path, reference_audio, reference_text. Create WAV, return audio path.
- Lipsync input: video, audio, output MP4 path, repo, python. Create MP4, return video path.

The orchestrator checks requested output files rather than trusting arbitrary returned paths.
No silent mock, no pass-through fallback for lip generation. Audio-only must be explicitly selected.
Adapters are supplied integrations, not GPU-validated builds. Freeze upstream commits after local validation.
