# Roadmap and completion gates

## Current release

The baseline is **recorded English–Hindi dubbing**, with human translation review, isolated model adapters, duration fitting, optional MuseTalk lip editing, exported captions and versioned delivery artifacts. The [design](DESIGN.md) describes current behavior and tradeoffs. [Validation](VALIDATION.md) distinguishes current measurements from inherited historical notes.

## Before the November 18 demonstration

1. Recover or reinstall the isolated model environments and approved weights on the actual presentation machine.
2. Record three permitted 10–20 second clips; collect exact English references and reviewed Hindi.
3. Run audio-only, then lip-synced generation. Save both immutable render directories and download bundles.
4. Apply the [evaluation](EVALUATION.md) gate: bilingual meaning/voice review and full temporal video review, not only sampled frames.
5. Record hardware, model commits, license/permission evidence, timings and any failed attempts.
6. Rehearse the [15-minute runbook](DEMO.md) with a genuine precomputed backup and explicit disclosure.

**Unresolved external dependency:** prior model assets and generated videos are on another inaccessible machine. Software tests alone cannot close the neural-demo gate.

## After the demonstration

| Milestone | Work | Acceptance evidence |
|---|---|---|
| Context-aware phrases | Group by semantic pauses, preserve names/pronouns, allow source transcript correction in UI | Paired adequacy ratings and fewer duration-rejection cases without meaning loss |
| Persistent model workers | Warm models once, track VRAM, bounded stage queues | Cold vs warm timing, stable memory on ten-minute input, no regressions |
| Visual continuity | Face tracking, overlap context and controlled seams across phrases | Full temporal reviews on motion/occlusion slices; reduced artifacts |
| Improved file replay | VAD-aware silence pass-through, pause-based chunks, failure summaries | Causal arrival checks, no unbounded backlog, reported overload instead of fake real time |
| Live transport | WebRTC capture, clocked audio/video buffers, disconnect handling, backpressure | Receiver-clock source-to-playback latency; 10-minute sustained run on defined hardware/network |
| Expanded evaluation | Held-out speakers and paired baseline comparisons | Per-slice results with sample sizes, uncertainty and critical-failure reporting |

Proposed live goals (not measurements): 25 FPS, median source-to-playback delay ≤6 s, p95 ≤8 s, and ≤1 s delay growth between minutes 2 and 10. Reassess feasibility after warm-worker benchmarks. Do not describe the current per-phrase subprocess baseline as meeting them.

## Replay today

```bash
python -m multilingua.cli --config configs/local.json replay input.mp4 --chunk-seconds 6 --max-waiting 2
```

Fixed windows are released after their source-time boundary; one worker calls the real adapters. `chunks.json` records arrival/start/ready times and output paths. Queue overflow stops the run. `replay.json` reports readiness delays; no continuous receiver/player is implemented. Automatic translation skips the UI review checkpoint, so use only permitted evaluation clips and review every resulting output before sharing. Silence-only chunks fail ASR. The separate `streaming.simulate` function evaluates scheduling costs only.
