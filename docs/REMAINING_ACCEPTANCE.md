# Remaining acceptance gates — 17 November 2026

Local models only. No cloud speech provider is used. English to Hindi dubbing only.

## Continuous dubbing

The current transport still uploads complete clips. `multilingua/streaming.py` is a scheduling simulator, not WebRTC. aiortc is not installed in the current service environment. Historical warm full-pipeline processing was 37.35 seconds per 5 seconds of input; lip processing alone was 31.47 seconds. Merely replacing transport cannot achieve 2–4 second delay at that throughput. No ten-minute real-time validation or dropped-frame claim is supported.

## Lip quality

No new restoration has been enabled. The previous faster LatentSync variants worsened measured alignment. Visual sharpness plus SyncNet on the same clips remains the acceptance gate, not an unsharp-filter implementation alone.

## Native review

The user confirmed no reviewer is available. Prepared local Hindi review bundles under `outputs/native-review-2026-11-17`, including exact output hashes and blank review CSVs. All approvals remain pending.

## Local configuration repair

Recreated ignored `configs/local.json` using existing model paths and Hindi FP16. Dependency-path diagnostics pass; this is not a new neural benchmark or a claim that a previously running process loaded the new configuration.

## Sentence timing repair

Preparation now groups adjacent unfinished ASR fragments into sentences before translation (maximum 12 seconds, gap at most 0.4 seconds). Original ASR segments are retained in `asr_segments.json`; existing reviewed jobs are not changed. This reduces artificial per-fragment timing failures but does not guarantee that every translation fits. The 1.25x speed cap remains. A separate revised copy of the failed 15-second clip completed at `/home/akash/A Nitin/multilingua/runs/441fcb47b140439882b207f2a21d9469`. Full FFmpeg video/audio decoding passed; native review remains pending.

## Demo speech preflight

Recorded rendering now generates and fits every speech phrase before invoking any lip model. Parler gets at most two alternative faster-delivery prompts, preserving reviewed text and the 1.25x fit cap. Per-candidate WAVs and speech_preflight.json files record the attempts. All remaining timing failures are reported together before expensive lip work. This does not implement semantic translation rewriting and cannot guarantee that arbitrary text fits. Existing overlap behavior remains available with speech_preflight=false. Tests verify zero lip calls on a later phrase failure and three total attempts maximum.

Studio enables one conservative Hindi coordination contraction as a final timing attempt (`संपर्क कर रहे हैं और उन्हें` → `संपर्क कर उन्हें`), logged separately as an AI edit with human review pending. This is a narrow rule, not a general semantic rewrite model. On the exact failing sentence, duration fell from 11.819 to 11.215 seconds and fit its 9.20-second slot at 1.219x. Audio-only test run 34896e2ed22f4463afbf1fe96a3f30cb completed and decoded; no new lip-quality claim is made from that test.

## Recorded phrase-boundary redistribution

The studio can now redistribute time within contiguous speech blocks after preflight failure. Minimum durations are rounded upward to the 25 FPS frame grid at the configured speed cap; every boundary may move by at most one second. Explicit silence blocks, speech order, text, block endpoints and video duration are preserved. If total capacity is insufficient or movement would exceed the bound, rendering still stops before lip generation. Reports record original and adjusted boundaries. The 29–30 s phrase in job 0bccc9d5ef8c4fcb80ed868524b0defe fits at 28.36–30 s after neighbouring boundaries move at most 0.64 s. This is a recorded-video timing adjustment, not live inference.
