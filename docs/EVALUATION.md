# Evaluation plan and honest reporting

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

## Separate three kinds of evidence

1. **Software correctness:** automated tests with fixed text and synthetic tones. They verify contracts, media timing, failure handling and UI flows.
2. **Model execution:** actual ASR/translation/TTS/MuseTalk runs with recorded hardware and revisions. A successful subprocess proves execution, not quality.
3. **Human usefulness:** bilingual review, listening and continuous video inspection. No automated infrastructure test replaces this.

Current results and unexecuted checks are in [VALIDATION.md](VALIDATION.md). Historical unbundled results remain explicitly attributed in [HISTORICAL_VALIDATION.md](HISTORICAL_VALIDATION.md) and [the upstream evaluation report](EVALUATION_REPORT.md). Its FLORES chrF++ sample and paired SyncNet comparison are preliminary evidence from the original workstation. The associated artifacts were unavailable for independent reproduction.

## Test-set slices

For tomorrow's demo, record **three permitted 10–20 second clips**: clean explanatory speech, names/numbers, and a technical sentence. Use one frontal speaker with deliberate pauses. These are a rehearsal set, not a generalization benchmark.

For subsequent evaluation, collect at least 30 short clips from 10 consenting adults, with separate development/test speakers. Include clean English, varied Indian English accents, names/numbers, technical vocabulary, moderate noise, mild head motion and occlusion. Label non-English speech, code-switching and unsupported multi-speaker/scene-cut inputs as boundary tests, not expected successes. Never tune speed caps or acceptance thresholds on the held-out test set.

The template [evaluation-manifest.example.json](../examples/evaluation-manifest.example.json) records clip identity, split, slice, permission reference, source hash and references. Keep actual faces, consent records and references outside Git unless publication is explicitly permitted. Record exclusions with reasons before scoring, including failures; do not evaluate only successful clips.

## Per-stage metrics and proposed launch thresholds

All quality thresholds below are **targets, not measured results**.

| Stage | Metric | Demo gate / target |
|---|---|---|
| Input | Decode success; source-audio presence; duration | 100% on permitted rehearsal clips; invalid input clearly rejected |
| ASR | Word error rate against human transcript; names/numbers exact-match | Clean-speech WER ≤15%; all critical names/numbers correct after review |
| Translation | Bilingual adequacy, fluency, omissions, factual consistency | Mean adequacy ≥4/5; no critical meaning reversal or changed numbers |
| TTS | Pronunciation and naturalness 1–5; missing words; rate ratio | Mean ≥3.5/5; no missing critical words; speed ≤1.25 |
| Timing | Source/output difference; raw speech/slot ratio | ≤120 ms final duration drift; zero silently truncated phrases |
| Visual | Continuous lip alignment, identity, flicker, mouth artifacts 1–5 | Mean ≥3.5/5; no identity failure or conspicuous broken frames |
| System | Prepare/render wall time, RTF, failures, peak VRAM | 3/3 real clips complete; target ≤10 min compute per 20 s clip; no OOM |
| UI | Upload → permission → prepare → review → render → download | Browser smoke succeeds; errors recoverable; no horizontal page overflow at 390 px |

ASR WER = (substitutions + deletions + insertions) / number of reference words. State tokenization, punctuation and case normalization rules before scoring. If chrF or COMET is added, record implementation, version and Hindi reference provenance. Do not invent a score from visual inspection of text.

RTF = compute seconds / media seconds. Report prepare time plus render time, and render-only RTF separately. A ratio below 1 does not demonstrate webcam latency. Causal replay reports source-window-end-to-ready delay, not playback delay. Future streaming requires receiver-clock measurements.

## Human review protocol

Use two bilingual reviewers where available; disclose if only one is available. Compare original, subtitles-only, audio-only and lip-synced clips using the **same reviewed text and voice**. Randomize A/B order and hide mode labels during quality ratings when practical; restore disclosure for any external viewing.

Rating anchors: **1** unusable/wrong; **2** major problems; **3** understandable but noticeable problems; **4** good with minor defects; **5** faithful/natural with no observed defect. A critical failure (changed negation, wrong number, unsupported claim, unconsented identity/voice, cut-off word) overrides the average and blocks release.

Listen once without video, watch once with sound, then inspect difficult transitions. Check the first and last words, pauses, bilabial closures, teeth, facial identity and abrupt phrase joins. Record per-clip results in [review-scorecard.csv](../examples/review-scorecard.csv), disagreements, revisions and final approval. Blank fields mean unmeasured, never zero. Have reviewers reassess after any text, voice or model change.

## Baselines and ablations

- **B0: reviewed Hindi subtitles over the original video.** Lowest compute; test whether viewers can follow speech and visuals.
- **B1: Hindi audio with original lips.** Isolates translation/TTS and exposes audiovisual mismatch.
- **B2: same Hindi audio with MuseTalk lips.** Paired comparison for added visual value.
- Later: compare raw duration mismatch to capped fitting, and fixed-window versus pause-based chunking. Do not disable the no-truncation gate merely to produce a favorable result.

Report sample size, exclusions, per-slice results, mean and range (or bootstrap confidence intervals for sufficient samples), failure rate and reviewer count. Avoid a single aggregate hiding weak slices.

## Reproducibility record

For each real run, save OS, Python, FFmpeg, GPU/driver, upstream Git commits, model revisions, package freezes, config hash, consent/source identifiers, source/output hashes, cold/warm state and measured wall times. `provenance.json` automatically captures hashes, Python and render metrics; model/driver/license evidence must be added to the operator's run record. Save `nvidia-smi` memory samples during inference for peak usage; a one-time idle query is not a peak-VRAM measurement.

The release gate is **software checks pass + real model runs + human approval**. If any leg is missing, demonstrate only what is verified and say which gate is pending.
