# Validation — 17 November 2026

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

## Earlier checkout validation (historical snapshot)

| Check | Result | What it establishes |
|---|---|---|
| `python -m unittest discover -s tests -v` | **55 passed** | Config, contracts, timelines, media, publication, replay, UI review, evaluation and experimental API behavior |
| `python tests/browser_smoke.py` | **Passed** on local Chrome | Upload, permission gate, editable Hindi, review reset, audio-only render, ZIP download, explicit lip failure, mobile layout; no JavaScript errors |
| `node tests/webcam_backpressure.cjs` | Passed | Model selection header, queue retry, requested capture duration and camera shutdown in the JS harness |
| `ruff check .` and `ruff format --check .` | Passed | Consistent syntax/import/style checks |
| `python -m compileall -q multilingua adapters scripts` | Passed | Python syntax; does not import heavy model libraries |
| `python -m build` | Wheel and source distribution built | Controller packaging; model assets/environments remain external |
| UI with missing configuration | Opened successfully | Actionable setup notice, system-check panel, no model fallback |
| Desktop and mobile inspection | 1440 px desktop and 390 px mobile | Readable layout, no mobile page overflow; screenshot in `docs/assets/studio.png` |
| `doctor` without configured models | Expected nonzero result | Honest setup status rather than a false-ready signal |

Test workstation: Linux, Python 3.11.16, Gradio 6.32.0, FFmpeg 9.0.2 (Conda-forge), local Google Chrome. `nvidia-smi` reports NVIDIA RTX 2000 Ada Generation with 16380 MiB. This verifies driver visibility, **not** successful neural inference or peak memory use. The repository's old `/home/akash/...` paths do not exist here.

The Gradio UI-build test emits an upstream asyncio `ResourceWarning` about an unclosed event loop in the test process; tests and browser flow complete. This is not a model or inference failure.

## Coverage highlights

- Malformed review shapes, non-string/empty translation, invalid timestamps and subframe speech are rejected.
- Hindi edits cannot alter locked English text, timestamps or row identity in UI requests.
- Permission is checked before UI preparation; review approval is required before generation and reset after Hindi edits.
- Adapter outputs are cleared before invocation; configuration cannot replace reviewed text or destination paths.
- Adapter timeouts produce actionable errors; Linux process-group cleanup is implemented.
- Render locks prevent same-job concurrency and release even when state is corrupt.
- Failed lip generation is a failure, never a successful audio-only fallback.
- A failed rerender preserves the previous video's subtitles, review record, alignment, provenance and mode.
- Real FFmpeg checks exercise silence gaps, audio stretching/padding, strict speed cap, concatenation and Unicode subtitles.
- Twenty fractional speech slots produce a bounded-duration final video without accumulating cut rounding.
- Successful lip-adapter orchestration uses an explicitly synthetic passthrough **only in a test**, not real lip generation.
- Precomputed export uses an independent folder and does not mutate published metadata.
- Causal replay releases a chunk after its source window; invalid config fails before a worker starts.

## Earlier environment limitations (historical)

No real faster-whisper, IndicTrans2, Indic Parler-TTS, IndicF5 or MuseTalk inference was executed in this revision's environment. Their weights and isolated environments are not installed here; the previous machine and its videos are inaccessible. The prior notes are preserved in the [historical record](HISTORICAL_VALIDATION.md) and [upstream evaluation report](EVALUATION_REPORT.md). The combined checkout’s camera capture, LatentSync inference, and resident model performance still require a real workstation rehearsal.

Consequently, no new claim is made for Hindi accuracy, voice quality, identity preservation, temporal lip quality, neural render speed, VRAM peak, or live playback. Changes to adapter revision handling and finite-audio checks are syntax-reviewed but still require model-environment execution. Full keyboard/screen-reader and bilingual accessibility review also remains pending.

CI configuration is included for Python 3.11/3.12, media tests, UI build, formatting, packaging and a synthetic browser workflow. Its remote execution status must be read from GitHub Actions; the local results above are independent of whether hosted CI has run.

## Current presentation workstation — 17 November follow-up

The local configuration now passes model-path diagnostics, and the NVIDIA RTX 2000 Ada reports 16380 MiB. This establishes installed paths and GPU visibility, not a new end-to-end neural benchmark. The earlier inaccessible-environment statements above describe the earlier checkout only.

The temporary authenticated studio was verified through its public HTTPS tunnel: login page HTTP 200, anonymous `/config` HTTP 401, successful login, and an authenticated configuration containing 53 components. The demo uses `runs/public-demo`, separate from earlier private studio jobs. This verifies access and authentication, not video generation or public queue completion. The public URL is ephemeral; credentials are not included in Git.

Current full regression run: **68 tests passed**; the Node webcam harness also passed. These checks use test doubles for neural stages and do not certify model quality.

Recent language-route checks: 3 tests passed, confirming Hindi acceptance and rejection of unsupported routes. All 18 then-existing Markdown documents and both language catalogs were checked for English → Hindi-only scope. This submission adds a separate index without changing the language scope.

## Demo release decision

**Submission documentation and software evidence are available; final neural-demo acceptance remains open.**

Close the remaining gate with three permitted clips on the actual presentation machine, saved real output comparisons, full-video review and fluent English–Hindi approval. Earlier real-model measurements in the evaluation/restoration reports are limited evidence; neither diagnostic checks nor synthetic tests establish natural lips, Hindi adequacy or realtime performance.
