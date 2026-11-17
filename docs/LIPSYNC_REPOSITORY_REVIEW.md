# Lip-sync repository review — 16 November 2026

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

The reported defect remains unresolved. Preserving beard texture is not evidence that lip generation or synchronization improved.

| Repository | Relevant approach | Local decision |
| --- | --- | --- |
| [ByteDance LatentSync](https://github.com/bytedance/LatentSync) | Version 1.6 trains at 512×512 specifically to mitigate blur; diffusion inference | Downloaded official source, isolated experimental runner. Official minimum is 18 GB; this card has 16 GB, so trying 8-frame batches and VAE slicing. Not enabled in webcam service. |
| [MuseTalk](https://github.com/TMElyralab/MuseTalk) | Current 256×256 generated face region; docs suggest disabling float16 for quality | Full-precision A/B render on the same original source and Hindi audio. Do not assume success from configuration changes. |
| [VideoReTalking](https://github.com/OpenTalker/video-retalking) | Separate lip synchronization and face enhancement stages | Candidate fallback, not installed or locally evaluated. |

LatentSync source revision: a229c3948406bc2cf6eaf4873e662e70c6a04746.
Test runner: adapters/latentsync_experiment.py. Its environment reuses existing .venv-voice libraries through a .pth file; it is an experimental compatibility setup rather than the upstream pinned environment. Reduced temporal context may affect consistency. The test retains 512px model resolution. No uploads of the user's footage to external services are needed.

Comparisons must use the same original recording and identical target audio. Inspect mouth opening/closure, teeth, facial hair, mask edges and temporal flicker; distinguish visual detail from SyncNet timing scores. Do not promote an alternative based only on its repository demos.

## MuseTalk full-precision result

Same 5.36-second clip, 134 face frames; 49.23 seconds inference. Visual inspection at 2 seconds shows no convincing mouth detail improvement. SyncNet distance was 8.994 for the previous result and 9.102 for full precision; confidence 2.894 versus 2.833, both estimated offset zero. These are short Hindi-clip proxies, not calibrated quality grades; the compared encoded audio lengths yield 130 versus 131 windows. No improvement established. Full precision remains opt-in and was not enabled in the webcam configuration.

## LatentSync setup

Official 1.6 checkpoint downloaded and SHA256 verified: `0a478e89eb660f82da4c35dbdde8a5adfb27f99d1b4e50edd03729e1e98316d3`. Official InsightFace buffalo_l detection and 106-landmark assets extracted with ZIP CRC validation; unused recognition model omitted. CPU face detection passed on the source frame. Model runs locally with PyTorch 2.6.0, VAE slicing, 8-frame temporal batches, 30 denoising steps, guidance 1.5 and seed 1247. This is a memory-adjusted experimental configuration, not the upstream default.

## Preview result — 17 November 2026

The initial 30-step full render completed inference but failed in upstream ImageIO video encoding. The experimental runner now saves generated frames and encodes using FFmpeg directly; a five-frame exporter smoke test passed. A 20-step, 2.4-second preview then completed in 200.73 seconds, with peak PyTorch allocated GPU memory 4.06 GB (not total device usage). It is not real-time.

Final files: runs/lip-quality/latentsync-preview-trimmed.mp4 and comparison.mp4. The corrected preview has exactly 60 video frames at 25 FPS and 2.4 seconds of audio. Same original source excerpt and identical Hindi WAV were used for both models. Sampled frames show more distinct lips/teeth with LatentSync; no human quality rating or full-video validation is claimed.

Final short-clip SyncNet report: runs/lip-quality/syncnet-final-preview/report.json. Minimum track threshold explicitly lowered from 100 to 30 frames for both clips. Both evaluated 57 windows. MuseTalk: minimum/zero-offset distance 8.964, confidence 4.331, estimated offset 0. LatentSync: minimum distance 8.948, zero-offset distance 9.991, confidence 4.726, estimated offset +1 frame (40 ms). This is mixed evidence: visual detail improved, but synchronization improvement is not established; zero-offset distance is worse. No timing correction was fitted to this single short clip. Earlier short-preview reports are superseded by this final report.

The live webcam backend remains MuseTalk. LatentSync is an isolated offline experiment, not a production switch or a completed fix for all lip-sync defects.

## App integration — 17 November 2026

The app now offers LatentSync and MuseTalk selection for webcam recordings and uploads. LatentSync uses the tested 20-step, eight-frame, 512px configuration through adapters/lipsync_latentsync.py. Each job persists an allowlisted model choice; requests cannot supply commands or filesystem paths. Recording durations: 6, 10 (default), 15, 30 seconds. Single-shot capture stops camera and microphone before processing, with a countdown, queued/processing elapsed-time messages, and download link. LatentSync is the UI default based on user preference. It is slow offline dubbing, not live webcam output. The backend accepts a 120ms container-padding allowance at the 30-second boundary.

Validation: 31 Python tests including model routing/invalid selection; JavaScript checks for model header, queue retry, selected duration, and track shutdown; adapter frame/audio handling verified using the actual saved LatentSync render in place of another costly inference. Browser visual inspection was unavailable because local browser use is disabled in Work settings. A full new GPU job through the UI has not been run.
