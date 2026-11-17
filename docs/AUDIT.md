# Repository audit and rubric mapping

Reviewed the full original tracked source tree: controller/UI/media/timeline/replay, all five model adapters and their protocol, both helper scripts, presets and historical package snapshots, tests, README, completion plan, validation history, license and packaging metadata.

## Findings and implemented improvements

| Area | Original finding | Improvement / evidence |
|---|---|---|
| Setup | Checked-in `/home/akash` paths and partial presets made a fresh clone unusable | Portable generic/reference examples, placeholder/environment expansion, ignored local config, structured diagnostics with exit status |
| Input contracts | Non-string reviewed values could pass preliminary checks and fail deep into rendering | Shared schema/size/timeline validation and actionable review errors |
| Request ownership | Model config could overwrite text/output fields in adapter payloads | Controller-owned fields take precedence; regression verifies exact reviewed text and destination |
| Stale files | A success response without new media could reuse a prior WAV/MP4 | Clear expected outputs and isolate every render attempt |
| Timeout cleanup | Parent timeout could leave nested MuseTalk processes running | New process session and group termination on POSIX |
| Publication | Failed rerender could leave old video with newly overwritten review metadata or wrong mode | Immutable render folders, atomic current pointer and coherent aliases; metadata/mode preservation tests |
| Timing | Independent cuts could accumulate frame rounding; allowed drift grew with number of segments | Quantize absolute frame boundaries; enforce fixed 120 ms final tolerance; 20-slot regression |
| Lock lifecycle | Corrupt job-state reads and finalization errors needed deterministic cleanup | State read under lock and nested-finally release; regression |
| Replay | Invalid worker config could terminate a thread without reliable error propagation | Initialize pipeline before thread; finite parameter validation; preserve explicit overload semantics |
| UI | Plain JSON editing, little guidance, no stage progress, no review acknowledgement | Bilingual table, protected source/timing, permission and review controls, progress, mode selection, responsive layout |
| UI state | Old outputs could appear while new work failed or source changed | Reset stale job/output state, invalidate approval on edits, serialize model events |
| Deliverables | Separate files with no simple export bundle or disclosure record | ZIP, SRT, reviewed text, alignment, hashes and AI-dubbed sidecar |
| Model reproducibility | Moving remote model names and little revision control | Translation/TTS revision options; snapshot guidance; honest external-dependency register |
| Speech boundary | Nonfinite/empty generation not explicitly rejected in TTS adapters | Finite, nonempty mono-array checks before WAV writing |
| Helper scripts | Hardcoded setup location; precomputed export could index speech incorrectly and mutate published metadata | Explicit MuseTalk path; timeline-based speech lookup; independent precomputed export folders |
| Maintainability | Dense one-line Python and no continuous checks | Formatted sources, Ruff config, pinned UI dependency set and CI |
| Documentation | Partial architecture and research plan, missing full rubric mapping and ready-to-use presentation script | Eight-part design, requirement IDs, diagram, tech register, evaluation plan/templates, setup and timed demo/Q&A |
| Evidence | README referenced ignored/nonexistent demo assets; historical records mixed claims and pending work | Separate current validation and attributed historical record; explicit remaining neural-demo gate |

## Demo guideline coverage

| Guideline | Evidence | Remaining presenter action |
|---|---|---|
| 1. GitHub code and link | Repository and focused commit history | Present the reviewed branch/merged revision |
| 2. Use-case/functionality document | README and DESIGN §1–3 | Rehearse the user problem in one sentence |
| 3. High-level architecture | Mermaid and static SVG with requirement IDs in design | Explain flow and human review checkpoint |
| 4. Documented stack | TECH_STACK, configs and adapter protocol | Record actual model revisions on the target machine |
| 5. Overview + working examples | DEMO timed runbook, recording scripts | Regenerate/recover real permitted outputs and rehearse |
| 6. Audience Q&A | DEMO question bank | Allocate topics to teammates and practice concise answers |
| 7. Implementation/design/demo/presentation quality | Tests, browser workflow, design, evaluation and presentation materials | Finish the real-model and human-quality gates |

## Eight-part design coverage

1. **Problem/users:** tasks, success conditions and unacceptable output in DESIGN §1.
2. **Why GenAI:** explicitly labeled five-criterion interpretation, pretrained/prompted choice, RAG/fine-tuning rejection and baselines in §2.
3. **Scope:** supported clips, excluded capabilities and boundary handling in §3.
4. **Requirements:** testable F1–F9 and targeted N1–N9 in §4.
5. **Architecture:** component interactions, requirements, state and tradeoffs in §5.
6. **Failures/guardrails:** recovery and residual risk matrix in §6.
7. **Evaluation:** slices, metrics, thresholds, baselines and review protocol in §7 and EVALUATION.
8. **Questions/risks:** explicit owners/actions/gates in §8.

## Deliberately unresolved

The original purpose and model roles are retained. No new language pair, cloud service, RAG system, model training or pretend live webcam capability was added. Existing model assets are unavailable, so real neural execution and human evaluation cannot be certified from this checkout. The default voice remains generic, and the UI is a trusted local prototype, not a production upload service.

Practical residual limits include per-phrase model reload cost, silent fixed-window replay failures, manual ASR corrections, no persistent job browser, no automatic speaker/consent verification, no burned-in watermark and local storage growth. These are documented, scoped limitations rather than hidden success claims.
