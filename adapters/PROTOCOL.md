# Adapter contract

Project scope: **English → Hindi only**. ASR requests use `en`, translation uses `eng_Latn` → `hin_Deva`, and TTS uses `hi`. Language fields describe this fixed route, not additional supported routes.

Each command is an argument array, followed by `--request FILE --response FILE`.
Read request JSON; write response JSON only on success; exit nonzero on failure.
Do not write credentials to logs. Config is trusted local code execution configuration,
never accept it from a network user. Each model runs in its own subprocess so package
conflicts are isolated and GPU memory is released when the process ends.

- ASR input: audio path and English language code (`en`). Output: segments with start/end seconds and text.
- Translation input: texts array, source `eng_Latn` and target `hin_Deva`. Output: texts array of equal length.
- TTS input: Hindi text, language `hi`, output WAV path, reference_audio, reference_text. Create WAV, return audio path.
- Lipsync input: video, audio, output MP4 path, repo, python. Create MP4, return video path.

The orchestrator checks requested output files rather than trusting arbitrary returned paths.
No silent mock, no pass-through fallback for lip generation. Audio-only must be explicitly selected.
Adapters are supplied integrations, not GPU-validated builds. Freeze upstream commits after local validation.

## Validation and revisions

The controller rejects malformed/empty text and invalid timelines before synthesis. It clears each
requested adapter output before invocation and keeps every render attempt in a fresh directory.
Stage settings cannot override the reviewed text, language or controller-owned output paths.
A timeout terminates the adapter process group on Linux, including nested lip workers.

Translation accepts `--revision COMMIT`; both TTS adapters accept `revision` in their JSON settings.
Parler's separate description tokenizer accepts `text_encoder_revision`. ASR supports explicit
snapshot paths via `--model`; pin the downloaded snapshot for reproduction. Use the exact MuseTalk
checkout commit, and record it with all auxiliary assets. Pinning weights does not automatically
pin every transitive remote-code or tokenizer dependency: inspect those separately.

Generated TTS arrays must be nonempty, finite and mono. Automated audio checks do not establish
intelligibility. Model adapters still require actual target-environment inference validation.
