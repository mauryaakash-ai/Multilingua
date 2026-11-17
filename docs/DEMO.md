# November 18 demo — 15-minute runbook

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

**Repository:** https://github.com/mauryaakash-ai/Multilingua
**Title:** Multilingua: Reviewable English–Hindi Video Dubbing

## Before class: go/no-go

- [ ] Rehearse on the actual presentation machine, projector and speakers.
- [ ] Run `python -m multilingua.cli doctor`; resolve required checks.
- [ ] Download approved weights beforehand; do not depend on classroom network access.
- [ ] Run three permitted short clips through real models. Confirm translations with a Hindi speaker.
- [ ] Listen to complete speech and watch complete lip-edited output, not just sampled frames.
- [ ] Save original, audio-only and lip-synced versions outside temporary upload storage; open each locally.
- [ ] Record actual timings, model revisions, source permissions and reviewer signoff.
- [ ] Keep the repository, README, design diagram and evaluation record ready in browser tabs.
- [ ] Silence notifications; check projector text size and audio volume.

**Current blocker:** the original repository references generated videos and model environments on another inaccessible machine. They are not included in Git. Until you regenerate or recover permitted assets, do not claim the neural demonstration is ready. The fallback walkthrough can demonstrate the UI and test results. Use the upstream evaluation report as attributed historical evidence and state that model playback is unavailable.

## Timed presentation

| Time | Presenter action | Key message |
|---|---|---|
| 0:00–1:30 | State problem, user and one use case; show repo | “We help educators adapt a short English explanation for Hindi-speaking learners.” |
| 1:30–3:00 | Show architecture; identify model roles and human checkpoint | “Generation handles speech and mouth pixels; a person controls meaning.” |
| 3:00–4:00 | Explain GenAI choice, scope and baseline | Pretrained specialist models; no RAG or fine-tuning; recorded video only |
| 4:00–6:00 | Upload a short clip, confirm permission, prepare, show/edit one Hindi phrase | Explain why numbers/names and translation length matter |
| 6:00–8:00 | Generate audio-only or lip mode if rehearsed runtime fits; show progress | Model loading dominates this offline baseline. Do not wait indefinitely. |
| 8:00–10:00 | Play saved original, audio-only and lip-edited versions from the same real run | Identify mode explicitly; show subtitles, artifacts and measured time |
| 10:00–12:00 | Show one controlled failure and evaluation evidence | Too-long speech stops rather than silently truncating; distinguish tests from quality ratings |
| 12:00–15:00 | Audience Q&A | Answer with evidence, acknowledge limits, offer a concrete next experiment |

If generation exceeds the rehearsed window, switch to a **previously rendered real output** and say so. Do not relabel precomputed results as live inference. If no real output exists, explain the model-access gap and show the verified UI/tests; this remains an incomplete neural demo.

## Suggested recording scripts

Record these yourself or with a consenting teammate, using natural pauses. These Hindi lines are draft examples and still need bilingual review.

1. **Everyday explanation:** “Good morning. Today we will learn how computers translate language. Please listen to the original video first.”
   Draft: “सुप्रभात। आज हम सीखेंगे कि कंप्यूटर भाषा का अनुवाद कैसे करते हैं। पहले मूल वीडियो सुनिए।”
2. **Numbers and negation:** “The workshop starts at ten, not eleven. Bring two notebooks. Registration is free.”
   Draft: “कार्यशाला दस बजे शुरू होती है, ग्यारह बजे नहीं। दो नोटबुक लाएँ। पंजीकरण निःशुल्क है।”
3. **Technical vocabulary:** “A model learns patterns from examples. We review its translation before generating the final video.”
   Draft: “मॉडल उदाहरणों से पैटर्न सीखता है। अंतिम वीडियो बनाने से पहले हम उसके अनुवाद की जाँच करते हैं।”

Use 10–20 seconds, steady framing, bright diffuse light, no background music, a visible unobstructed mouth and an extra pause at each end. Never imply the generic voice clones the source speaker.

## Q&A practice

**Why not subtitles alone?** They are our lowest-cost baseline. Dubbing reduces reading burden; lip editing should earn its additional compute through better viewing experience. We plan paired user ratings.

**Is it real time?** No. The studio processes recorded clips and reloads models per phrase. The optional webcam service finalizes a recording before processing it. Warm workers reduce loading time, while continuous low-latency dubbing still requires measurement.

**Why no RAG or agent framework?** The source speech supplies the content. This is a fixed media transformation workflow, not external knowledge retrieval or autonomous planning.

**What is your contribution?** A reviewable integration: adapters across isolated environments, bounded duration fitting, explicit failures, coherent render artifacts, a review UI and reproducible evaluation. We did not train the underlying models.

**What if Hindi is longer than English?** We measure generated speech. Up to 1.25× acceleration is allowed; longer speech is rejected for a shorter, meaning-preserving translation.

**How do you measure quality?** ASR reference errors, bilingual adequacy, speech naturalness, temporal lip/identity inspection, timing drift and runtime. Report only measured results, with sample size and reviewer count.

**What can fail?** Accent recognition, names, code-switching, missing faces, flicker and model access. Point to one observed failure and the applicable guardrail.

**What happens to my video?** It is processed through local adapters. Downloading weights requires network access during setup. Local jobs remain on disk until deleted; this is not a public upload service.

**What would you improve next?** Context-aware phrase grouping and persistent workers, evaluated on held-out speakers. Live transport comes only after clocked scheduling and sustained latency measurements.

## Team handoffs

For three presenters: A owns problem/design (0–4 min), B owns demonstration (4–10 min), C owns evaluation/risks (10–12 min); everyone answers their component's questions. Rehearse the handoff sentence and cap answers at 30–45 seconds before inviting follow-up. With fewer presenters, keep the same timing and allocate roles explicitly.
