# Measured realtime roadmap

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

Requested 17 November 2026. Targets are acceptance criteria, not current capabilities: pipeline RTF <1; 2–4 s live delay; 25 FPS; lip alignment no worse than baseline; English → Hindi only.

1. **Profile** — ten same-process calls per stage, first excluded; synchronize GPU timings; distinguish load, cold call, warm call and memory. Baseline scripts: benchmarks/run_baseline.py and benchmarks/profile_stage.py. Raw outputs: runs/profiling/baseline. Isolated stage peaks do not establish simultaneous memory fit.
2. **Persistent workers** — one coordinator, bounded queues and resident model workers in their compatible environments. Preserve request/response logs. Compare the same 5-second source and target audio, then test multi-phrase throughput. Validate simultaneous GPU memory before enabling overlap. CPU ASR/translation remain valid if their measured RTF is already below one.
3. **Mouth detail** — evaluate crop changes, restoration, colour correction and temporal smoothing separately, against plain MuseTalk. In v1.5 the stock inference script forces bbox_shift=0. EMA can introduce lag; do not assume it fixes motion. Reusing avatar face/latent caches applies to identical prerecorded reference frames, not unseen live webcam frames. Treat those as separate benchmarks.
4. **Voice/VAD** — distinguish ASR disagreement from speech errors using a stronger recognizer and listening. Preserve no-truncation and speed limits. User selected local models only: exclude paid/cloud streaming TTS comparisons. IndicF5 needs an authorized reference voice. Silence must be a normal live event. Native-speaker acceptance cannot be fabricated by an automated test.
5. **Hindi evaluation** — evaluate English → Hindi translation and Hindi speech separately. Keep the fixed English input / Hindi output configuration. Approval by a fluent English–Hindi reviewer remains pending until actually performed.
6. **Streaming** — continuous transport, audio clock, bounded buffering/cancellation, and a 10-minute run with measured latency distributions. An offline cached-avatar FPS result does not establish continuous arbitrary-webcam latency.
7. **Recorded quality** — retain LatentSync; independently benchmark step count, guidance, caching and compilation. Existing 20-step preview and 10-second job are baseline evidence only.

## Recent model check

- LipForcing official README: https://github.com/cvlab-kaist/LipForcing. Released 14B model reports approximately 37 GB with precomputed text embeddings and was tested on H200; 1.3B weights remain unchecked on its roadmap. The 31 FPS claim is for the smaller variant, not evidence that the released model runs on this 16 GB GPU.
- EfficientSync project: https://alunaticat.github.io/EfficientSync/index.html. Public demo page inspected; downloadable implementation/weights have not been established from that page. Do not treat a research demo as an available drop-in backend.

No fine-tuning has been established. An optional recorded-video GFPGAN experiment is available, OFF by default; see [measured restoration results](WEBCAM_RESTORATION.md). It does not establish natural lips or realtime performance.

## Measured progress

Baseline measured: runs/profiling/baseline/REPORT.md. Warm ASR 0.760 s, translation 0.374 s, TTS 6.026 s, MuseTalk 18.568 s, final FFmpeg encode/mux 0.153 s on a 5-second fixture. MuseTalk UNet+decode alone costs 57.84 ms/frame. This rules out treating model reload as the sole bottleneck. TTS peak Torch allocation 4.179 GiB; MuseTalk 2.660 GiB separately. Integrated residency subsequently peaked at 13,309 MiB total device use, including desktop allocations.

Resident adapters are integrated into Pipeline and the local server launcher. The complete 5-second job measured 59.765 s cold and 41.019 s warm (RTF 8.204), with the same four worker PIDs. See runs/profiling/integrated/report.json. Startup remains lazy; no startup warm-up or avatar latent cache is implemented. Bounded next-phrase TTS prefetch and cancellation are implemented; cross-job stage overlap is not. Phases 3–7 acceptance criteria remain unfulfilled.


## Local-only follow-up measurements

- Parler float16: 3.143 s warm versus float32 6.026 s on the profiling phrase, peak Torch allocation 2.108 GiB. Same-reference large-v3 round-trip WER was 23.08% versus 30.77% for float32. One short phrase is insufficient to establish perceptual equivalence; the adapter supports explicit dtype selection, retaining float32 as its default.
- IndicF5: 10.100 s warm for 5.76 s generated audio, using its shipped generic demo reference. Different voices prevent a controlled identity comparison. It was slower than Parler and is not selected.
- Stronger ASR: Rohit WER 50.0% (small) versus 19.74% (large-v3) on identical audio. Divya large-v3 WER 29.63%. These measure recognizer sensitivity, not human intelligibility or TTS ground truth. Raw results: runs/evaluation/recognizer-comparison/report.json.
- Silero offline VAD produces pause-based segments and returns empty segments on silence. Silent pipeline jobs return the original video. This is not yet streaming ASR/VAD transport.
- The supported evaluation route is English → Hindi. Native Hindi review and broader reference-based chrF++ evaluation remain pending.
- LatentSync guidance 1.0 at 10/12/15 steps took 72.777/85.362/99.102 s for 2.4 s. SyncNet minimum distances were 10.504/10.367/10.401 and confidences 2.924/3.007/3.028, worse than the prior 20-step guidance-1.5 baseline (8.948, 4.726). Keep the existing quality preset. Short-clip metrics alone cannot establish general quality.

Still required: broader mouth-restoration validation, cached reference preparation, streaming English ASR and duration-aware Hindi translation, continuous WebRTC output, a bounded-delay 10-minute run, and native-speaker reviews. No realtime completion claim is supported by current measurements.

Integrated float16 follow-up: cold 71.145 s; warm 37.350 s for 5 s input (RTF 7.470), TTS 3.273 s and lip adapter 31.474 s. Peak total device use 10855 MiB. The Hindi local config selects float16. The service has been restarted with resident workers; models load lazily on the first job.
