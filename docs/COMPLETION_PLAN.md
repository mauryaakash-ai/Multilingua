# Implementation and completion plan

## Project definition
Multilingua: Duration-Aware English–Hindi Video Dubbing with Lip Synchronization.
Input: one English-speaking visible adult speaker, clear audio, frontal face.
Output: Hindi speech, edited lips, subtitles, segment metadata and measured processing times.
First release is recorded-video dubbing. Real-time webcam dubbing remains a distinct research milestone.
This project does not yet support arbitrary language selection, overlapping speakers, face tracking across
cuts, preservation of background music, or WebRTC transport.

## What is supplied and what is not
| Component | State |
|---|---|
| FFmpeg normalization, segmentation, audio fitting, muxing | Implemented; synthetic integration tests |
| Transcript and translation review | Implemented through JSON and optional local Gradio UI |
| ASR / IndicTrans2 / IndicF5 / MuseTalk integrations | Implemented adapters; require external environments, weights and GPU validation |
| Job state, logs, failure propagation, render locks | Implemented and tested where reported |
| Bounded queue analysis and causal file replay | Implemented; replay writes per-chunk outputs and timings, not a continuous media server |
| Live capture, streaming ASR, persistent GPU workers | Planned, not implemented |
| Lip quality, Hindi quality, actual FPS, latency claims | Unmeasured until run on real inputs and target hardware |
| Production authentication, deployment and multiple users | Outside this local research release |

## Architecture and contracts
The controller invokes each adapter as a subprocess using a JSON request/response protocol.
ASR and translation execute once per job. TTS and lip generation currently execute per phrase.
This intentionally trades speed for dependency isolation and low peak shared GPU occupancy.
Models reload per invocation; this design is an offline baseline, not a low-latency architecture.
Subprocess exit releases GPU memory, useful on a 16 GB card. CPU ASR and translation are initial defaults.
Do not assume 16 GB guarantees MuseTalk compatibility for every clip or model version.

Each job owns source.mp4, source.wav, job.json, segments.json, reviewed_segments.json,
segment_XXXX directories, output.mp4, subtitles.srt, alignment.json and per-adapter logs.
Job states: preparing -> awaiting_review -> rendering -> complete; any failure -> failed.
The review JSON is the correction interface: modify translation, retaining start/end timestamps.
There is no hidden fake translation, fake lip edit, or automatic fallback after a failed neural adapter.

## Timing policy
For a source interval [s,e], slot duration is e-s. Measure synthesized audio duration D.
If D <= slot, preserve speaking rate and pad silence. If 1 < D/slot <= 1.25,
apply FFmpeg atempo so speech fits. If D/slot > 1.25, stop with a review error.
Do not silently trim meaning or aggressively accelerate speech. A shorter correct translation
must be supplied before retrying. Lip generation consumes the final fitted audio, never the raw TTS.
Original gaps are preserved with silence. Original background audio is currently removed.
Frame quantization at 25 FPS can accumulate small duration errors. Integration checks detect excessive
drift; production streaming needs a global clock and sample/frame-exact scheduling.

## Milestone 1: reproducible baseline (estimated 1 week)
1. Record 3 consented 20–30-second English clips: frontal, mild head motion, technical vocabulary.
2. Create isolated environments. Download official model weights and save model/repo revisions.
3. Verify ASR against a manually checked transcript; run translation and correct the Hindi.
4. Run audio-only generation and listen for pronunciation, pace and missing words.
5. Enable MuseTalk and inspect mouth closures, teeth, moustache, identity and frame transitions.
Acceptance: three real videos finish; no synthetic test doubles; audio duration within declared tolerance;
outputs understandable to a Hindi-speaking reviewer. Save logs and exact versions.

## Milestone 2: phrase continuity and quality (estimated 1–2 weeks)
1. Compare ASR segment boundaries against pauses and semantic phrase boundaries.
2. Add configurable phrase grouping with maximum duration and context window.
3. Implement duration-aware translation candidate generation, retaining a meaning check and human review.
4. Add overlap context around each video phrase; crop only final central frames to remove seams.
5. Add explicit face-detection confidence and occlusion handling. A failed face edit should be reported;
if an audio-only fallback is chosen, mark the output and metadata as such.
Acceptance: fewer visible boundaries than baseline; no missing speech; no cumulative timing growth.

## Milestone 3: causal replay (estimated 1–2 weeks)
Feed recorded media as timestamped chunks only when their capture window closes. Never let the model
read future audio or future video. Existing offline processing of the entire file is not this test.
Replace subprocess-per-phrase model loading with persistent workers and warmup.
Use a bounded queue per stage and a shared monotonic clock. Record arrival, start, finish and playback.
The `replay` CLI implements this fixed-window baseline with bounded queues and records ready-delay metrics.
It writes separate chunk outputs; continuous playback and persistent workers are still required.
The additional simulator estimates queue growth from measured stage costs without inference.
Acceptance: ten-minute stream with no unbounded queue growth; report cold start separately from steady state.
If sustained service time exceeds incoming chunk duration, declare overload instead of claiming real time.

## Milestone 4: live transport (estimated 2 weeks)
Use browser getUserMedia + WebRTC/aiortc (or a native capture application) for timestamped audio/video.
Separate audio ingress, phrase commitment, translation, TTS, face tracking, lip generation and egress workers.
Use ring buffers for source video and sample-indexed audio; output both from one playback clock.
Do not use MediaRecorder time-slice fragments as standalone video files without handling container headers.
Implement disconnect, cancellation, model failure, reconnect, bounded queues and backpressure.
A receiver should display current delay and selected target language. Never show a fake FPS counter.
Start one-way with one speaker. Two-way calls require echo control and interruption policies and are later work.
Acceptance target (not measured promise): 25 FPS output; median source-to-playback delay <=6 seconds;
p95 <=8 seconds; no >1-second latency growth between minute 2 and minute 10 on a controlled LAN.
Tune these targets after the first hardware benchmark; report failures honestly.

## Milestone 5: experiments and submission (estimated 1–2 weeks)
Collect 10–20 consenting speakers with 3–5 clips each; do not call this a training-scale dataset.
Include English accents, Hindi names, code-switching, technical vocabulary, noise, head motion and occlusion.
Hold out speakers for final testing; use validation for thresholds and never tune on the final test set.
Compare audio-only, fixed chunks, pause-based chunks, and duration-aware chunks on identical clips.
Ablate duration fitting and adaptive segmentation independently. Keep model versions and hardware constant.

Metrics:
- ASR WER against corrected transcripts; report code-switched errors separately.
- Translation: bilingual adequacy ratings and a documented metric such as chrF/COMET with references.
- Speech: naturalness and pronunciation human ratings; record rate-adjustment ratio.
- Lip sync: SyncNet/LSE-style measurement with exact implementation and held-out language validation.
- Video: identity, flicker and mouth artifacts judged by humans; image metrics alone are inadequate.
- System: sustained processing FPS, first-result delay, p50/p95 end-to-end delay, maximum queue depth,
  peak VRAM, dropped frames and real-time factor (compute seconds / media seconds).
Do not report offline render real-time factor as a measure of conversational latency.
Report absolute results, paired comparisons, sample size and variability; never invent numbers.

Final submission: source code; environment lockfiles; reproducible commands; dataset manifest and consent
records; architecture; baseline comparisons; ablations; failures; 2–3-minute demo; report and presentation.
Make the demonstration include actual source and output with a visible timestamp/delay measurement.

## Research question
Can adaptive phrase commitment plus duration-aware translation reduce delay and duration mismatch
for English–Hindi lecture dubbing while preserving meaning and visual synchronization?
This is a proposed contribution, not a claim of novelty. Compare against directly related pipeline work.

## Risks and decisions
- More natural translation needs more context; shorter chunks may reduce accuracy.
- Hindi TTS duration may exceed English slots; measured duration must guide a revision, not just text length.
- Per-phrase face generation can flicker; contiguous frame state/context is needed for the streaming version.
- Multiple target languages multiply TTS and visual compute even if source ASR is shared.
- Download availability, gated access and third-party licenses must be resolved for chosen versions.
- Use consented speakers/reference voices. Label shared outputs as AI-dubbed.
- Binding the Gradio prototype to a public interface is not supported; add auth and upload limits first.

## Reading list (official sources, accessed 6 November 2026)
- MuseTalk: https://github.com/TMElyralab/MuseTalk
- MuseTalk inference contract: https://github.com/TMElyralab/MuseTalk/blob/main/scripts/inference.py
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- IndicTrans2: https://github.com/AI4Bharat/IndicTrans2
- IndicF5 model card: https://huggingface.co/ai4bharat/IndicF5
- LatentSync: https://github.com/bytedance/LatentSync
- StreamSpeech: https://aclanthology.org/2024.acl-long.485/
- SeamlessStreaming: https://github.com/facebookresearch/seamless_communication
- Length Aware Speech Translation for Video Dubbing: https://www.isca-archive.org/interspeech_2025/subramanian25_interspeech.pdf
- Asynchronous multilingual pipeline: https://arxiv.org/abs/2512.18318
- HDTF: https://github.com/MRzzm/HDTF
- IndicVoices: https://huggingface.co/datasets/ai4bharat/IndicVoices

Estimated timeline is a planning estimate for a student project, not a completion guarantee.
