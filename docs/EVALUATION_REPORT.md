# Evaluation and delivery status — 16 November 2026

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

This is a working recorded-video prototype with preliminary measured evaluation. It is not a
validated real-time or production service. Three public HDTF development speakers were tested;
all were used during debugging, so none is a held-out final test speaker.

## Translation
IndicTrans2 en-indic dist 200M scored **63.1676 chrF++** on 32 evenly spaced FLORES-200 development
sentences selected before scoring. Professional Hindi references were used, with no fine-tuning
on this sample. This is not the full benchmark, a COMET score, or an end-to-end dubbing quality score.
SacreBLEU signature: `nrefs:1|case:mixed|eff:yes|nc:6|nw:2|space:no|version:2.6.0`.
References, hypotheses and exact sample indices are saved in `runs/evaluation/translation-report.json`.
The original archive URL and checksum are in `datasets/flores200/provenance.json`.
IN22 access returned HTTP 403; FLORES was used as an accessible independent reference set.

## Lip synchronization
Official `joonson/syncnet_python`, revision `907c0b579c2e2d83f0eae1b2ac9e720cde4e5623`.
Official face-track crops, 25 FPS, offset search ±15 frames (±600 ms), one visible face track per clip.
Reports include checkpoint hash, zero-offset distance and number of evaluated windows.
Lower minimum distance and higher confidence indicate stronger correspondence; there is no
universal pass threshold here. Hindi-specific calibration and human temporal review remain pending.

| Clip | Min distance | Confidence | Estimated offset |
|---|---:|---:|---:|
| Original English, Radio3 | 6.276 | 10.206 | −40 ms |
| Hindi audio, unchanged English lips | 14.961 | 0.580 | +80 ms |
| Hindi audio, MuseTalk-edited lips | 8.346 | 6.499 | 0 ms |
| Radio1, generic female Hindi voice | 8.938 | 4.103 | +40 ms |
| Radio4, repaired final output | 9.368 | 4.246 | +40 ms |

The paired Hindi comparison supports improvement on that clip. English source scores are a
contextual baseline, not a language-matched threshold. The third speaker's final repaired score is saved in `syncnet-radio4-fixed/report.json`;
the earlier measurement in `syncnet-additional/report.json` is explicitly superseded.

## Voice consistency proxy
Independent Hindi transcription using Whisper-small was compared with the intended Hindi text.
Normalization is NFKC, casefold and punctuation removal; CER excludes whitespace and counts codepoints.

| Generic voice / clip | WER | CER |
|---|---:|---:|
| Rohit / Radio3 | 42.11% | 16.87% |
| Divya / Radio1 | 70.37% | 19.85% |

These high error rates need investigation. They combine ASR weaknesses, pronunciation, spelling,
word segmentation and timing changes; they are neither a human intelligibility score nor a voice
naturalness MOS. No human scores were fabricated. Source-English WER remains unscored without
independently corrected transcripts. Samples start/end mid-sentence, another evaluation limitation.

## Multi-speaker and failure findings
Source manifest: `datasets/hdtf/development_manifest.json`. All clips are development excerpts,
not an official HDTF split. Generic voice presets were selected; original speakers were not cloned.
- Radio3: 30 seconds, generic male voice, 750 frames.
- Radio1: 15 seconds, generic female voice, 375 frames. Automatic Hindi exceeded one slot;
  a shorter assistant-reviewed translation succeeded. Original failure state was retained.
- Radio4: 15 seconds, generic female voice, final 375/375 frames preserved. Sentence fragments required grouped translation.
  Testing found a sub-frame trailing gap and upstream floating-point frame loss; both were fixed.
- Source/output still frames were visually inspected for gross face-placement errors. This does
  not certify temporal smoothness, voice suitability, or identity preservation.
- Three frontal speakers cannot establish broad robustness. Head turns, occlusion, accents,
  background noise, overlapping speakers and an independent speaker-held-out set remain needed.

## Webcam and HTTP service
`multilingua/server.py` and `web/index.html` add an authenticated, single-operator, bounded queue.
The browser finalizes each six-second recording into an independent container. It does not send
headerless MediaRecorder fragments as standalone videos. Capture stops on overload; the error
is visible rather than allowing unlimited delay growth. Webcam/microphone require a user click
and browser permission. Live camera capture itself has not been exercised on the user's devices.

A real authenticated HTTP upload produced a five-second dubbed video in **52.299 seconds**
(**RTF 10.46**, actual source video duration 5.0 seconds), preserving 125/125 frames and audio/video
durations. Earlier attempts correctly failed on overlong speech. The automatic server now may
use available leading/following silence, preserving the 1.25x speed cap and next-phrase boundary;
original requested timestamps and effective timestamps are both recorded. Arbitrary clips may
still require translation review. Stopping capture does not cancel already-submitted GPU jobs.

This is **not sustained real-time dubbing**. Persistent model workers, continuous WebRTC output,
optimized detection/compositing, cancellation, and ten-minute latency/overload validation are
unfinished. Cold model loading and serial processing remain significant costs. Some additional-speaker runs
overlapped other evaluation work; their timings are observed runs, not isolated hardware benchmarks.

## Software and deployment
30 unit/integration tests passed, including timing regressions, failures, authentication, input
validation and queue saturation. Neural results above are separate from the synthetic test suite.
The new frontend passed JavaScript syntax checking; HTTP endpoints were exercised. Embedded-browser
Basic-auth support prevented a browser walkthrough, so no webcam usability test is claimed.

`deploy/` contains a systemd/Caddy deployment candidate. No public host, DNS, or paid resources
were created because the user has not selected a provider or budget. It still needs deployment-host
GPU validation, HTTPS checks, retention/quotas, monitoring and release review. It is not a
multi-tenant production system. The existing Gradio UI remains for local recorded-video review.

## Reproduction and sources
- SyncNet implementation: https://github.com/joonson/syncnet_python
- FLORES benchmark and licensing: https://github.com/facebookresearch/flores/tree/main/flores200
- HDTF metadata: https://github.com/MRzzm/HDTF
- `scripts/evaluate_syncnet.py`, `scripts/evaluate_hindi_speech.py`, `scripts/evaluate_text.py`
- `configs/evaluation-environment.lock.txt`, model and dataset provenance JSON files
- `patches/musetalk-frame-rounding.patch` is a local change to the pinned MuseTalk checkout.
