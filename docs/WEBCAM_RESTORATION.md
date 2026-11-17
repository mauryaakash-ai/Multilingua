# Webcam mouth-restoration experiment

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

The inspected webcam job is `8cf47a73c510435db924f4d5df79488e` (10.72 s, 1920×1080). A source/output frame at 4 s shows softer generated lips and changed moustache detail. This frame inspection does not establish temporal alignment quality.

Existing production path already has a mouth segmentation mask and mild unsharp enhancement. MuseTalk v1.5's upstream inference fixes `bbox_shift=0`; tuning the old v1.0 setting would not change this path.

`scripts/benchmark_mouth_restoration.py` is an **experimental post-process**. The studio now offers it as an optional recorded-video checkbox, OFF by default. GFPGAN restores an aligned whole face and only a feathered mouth region is pasted back. The rest of the frame comes from the existing dubbed video. Optional bounded colour-offset matching and low-weight, change-gated temporal blending are separate benchmark ablations; neither is enabled by the studio adapter. Temporal smoothing is disabled by default. Restoring shape cannot guarantee correct phonemes, original teeth, lip colour or identity.

Dependencies are isolated under `vendor/restoration-deps`; checkpoints are under `models/restoration`. The official GFPGAN v1.4 checkpoint and facexlib detector/parser are used. Background upscaling is disabled. This initial experiment is float32 and is not TensorRT-exported.

Controlled sample: 3–6 s from the same completed webcam output; audio and video are reused rather than regenerating speech or MuseTalk. Baseline SyncNet minimum distance 8.37155, confidence 5.62187, zero-offset distance 11.81616, selected offset −1 frame. These scores are specific to this short sample and are not calibrated Hindi acceptability thresholds.

Artifacts: `runs/quality-webcam-review/`. Evaluation must include zero-offset distance, visual comparison, face-detection failures and synchronized GPU milliseconds per frame. Laplacian variance is only a sharpness proxy; invented texture can increase it. The 40 ms/frame target includes all inference, not just post-processing.

Official references:
- https://github.com/TMElyralab/MuseTalk
- https://github.com/TencentARC/GFPGAN
- https://github.com/TencentARC/GFPGAN/blob/master/gfpgan/utils.py

No fine-tuning, training-data preparation, tighter-crop model change, avatar caching or real-time capability is established by this experiment. Those require separate controlled validation. Training needs footage permitted for that purpose.


## Measured results

Paired three-second sample (identical PCM audio, 71 SyncNet windows):

| Variant | Min distance ↓ | Confidence ↑ | Zero-offset distance ↓ | Extra ms/frame |
|---|---:|---:|---:|---:|
| Existing MuseTalk | 8.372 | 5.622 | 11.816 | — |
| GFPGAN with full-frame paste | 8.390 | 5.644 | 11.896 | 312.0 |
| GFPGAN with 640px detection / mouth-only warp | 8.332 | 5.802 | 11.820 | 109.6 |
| Above + colour adjustment | 8.652 | 5.545 | 12.137 | 108.3 |
| Above + temporal smoothing 0.08 | 8.549 | 5.442 | 11.945 | 109.4 |

Whole 10.72-second webcam clip (identical PCM audio, 264 windows): baseline minimum distance 8.593, confidence 4.691, zero-offset distance 10.686. Restoration-only: 8.368, 4.797, 10.500. Both selected −1 frame offset. All 268 frames had a detected face. Extra restoration/compositing cost averaged 103.10 ms/frame, excluding encoding and muxing.

The inspected paired frame shows clearer tooth/lip edges, but this is modest and not a calibrated perceptual result. Mouth Laplacian variance **decreased** on the short sample (11.19 to 8.14 for the efficient variant); therefore no blanket numerical sharpness-improvement claim is supported. Colour matching and temporal smoothing did not pass the comparison and remain disabled. The added cost fails the 40 ms/frame live budget before counting MuseTalk itself.

The studio adapter invokes only restoration-only efficient mode at strength 0.65, evicts the resident MuseTalk worker before restoring to avoid overlapping GPU model allocations, validates duration, and records enhancement settings/model hash in provenance. Audio-only and silent jobs skip enhancement. No general Hindi lip-quality claim across speakers is supported by this one-clip test.

Preview: `runs/quality-webcam-review/comparison.mp4`; full restored video: `webcam-restored.mp4`; paired metric reports: `paired-sync/report.json` and `full-sync/report.json`. Model SHA256: e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad.
