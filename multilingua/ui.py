"""Local, single-user dubbing studio. Model work is serialized across UI events."""

from pathlib import Path

from .config import diagnose
from .pipeline import Pipeline, read_json, write_json
from .timeline import validate_segments

CSS = """
.gradio-container {width: 100% !important; max-width: min(1220px, 100vw) !important; margin: auto;}
body {background: #f5f7fa;}
#masthead {background: #102b3b; color: #fff; border-radius: 20px;
  padding: 32px 36px; margin: 10px 0 18px;}
#masthead h1 {font-size: clamp(30px, 4vw, 46px); letter-spacing: -1.7px;
  line-height: 1.15; margin: 12px 0; font-weight: 750; color: #fff;}
#masthead p {color: #c9dce4; max-width: 700px; font-size: 16px; line-height: 1.6; margin: 0;}
.eyebrow {font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #87e4ca;}
.pills {display: flex; gap: 8px; flex-wrap: wrap; margin-top: 24px;}
.pill {font-size: 12px; color: #e4f3f5; padding: 5px 12px; border: 1px solid #49616e; border-radius: 24px;}
.flow {display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 8px 0 20px;}
.flow-item {display: flex; gap: 12px; align-items: center; background: #fff;
  border: 1px solid #dce4ea; border-radius: 12px; padding: 16px; color: #1d3543;}
.flow-item b {font-size: 14px;} .flow-item small {display:block; color: #536a79; margin-top: 3px;}
.step {width: 32px; height: 32px; border-radius: 50%; background: #e4f5ef;
  color: #17604b; display: grid; place-items: center; flex-shrink: 0; font-weight: 700;}
#status {border-left: 4px solid #24866d; background: #edf6f2; padding: 12px 16px; border-radius: 8px;}
#status p {color: #173c30; margin: 0;}
#setup-note {background: #fff6e5; border: 1px solid #ecd7a7; padding: 12px 16px; border-radius: 8px;}
#setup-note p {color: #694e1c; margin: 0;}
.section-label {font-size: 11px; letter-spacing: 1.5px; color: #526b7a; font-weight: 700; margin: 14px 0 8px;}
#review-table {font-size: 15px;}
#review-table .table-container {overflow-x: auto !important;}
#review-table .table-wrap {min-width: 1000px;}
#footer {text-align: center; color: #526b7a; font-size: 12px; padding: 20px 0 8px;}
@media (max-width: 640px) {
  #masthead {padding: 24px;} .flow {grid-template-columns: 1fr; gap: 8px;}
  .flow-item {padding: 10px 14px;} #masthead h1 {letter-spacing: -1px;}
}
"""


def review_rows(segments):
    return [
        [i + 1, s["start"], s["end"], s["text"], s["translation"]] for i, s in enumerate(segments)
    ]


def reviewed_segments(rows, original, duration):
    """The browser cannot change source text, row identity or timing."""
    if not isinstance(rows, list) or len(rows) != len(original):
        raise ValueError("Keep every original row; edit only the Hindi translation column.")
    result = []
    for index, (row, segment) in enumerate(zip(rows, original)):
        expected = [index + 1, segment["start"], segment["end"], segment["text"]]
        if not isinstance(row, list) or len(row) != 5 or row[:4] != expected:
            raise ValueError(
                f"Row {index + 1}: edit only the Hindi translation; source and timing are locked."
            )
        result.append({**segment, "translation": row[4]})
    return validate_segments(result, duration, translated=True)


def readiness_markdown(report):
    required = [c for c in report["checks"] if c["required"] and not c["ok"]]
    if required:
        return (
            f"**Setup needed · {len(required)} checks to resolve.** "
            "You can explore the studio. Open **System check** before running model inference."
        )
    return "**Local paths checked.** Run a short real clip to verify model access and quality."


def build_app(config="configs/local.json", runs="runs", resident_pool=None):
    import gradio as gr

    runs = Path(runs).resolve()
    report = diagnose(config)

    def prepare(video, consent, progress=gr.Progress()):
        # Clear earlier job/output before any operation that might fail.
        yield (
            "",
            [],
            None,
            None,
            None,
            "**Preparing your video…**",
            gr.update(interactive=False),
            {},
            False,
        )
        try:
            if not video:
                raise ValueError("Upload an English video first.")
            if not consent:
                raise ValueError(
                    "Confirm permission to process and dub the video before continuing."
                )
            pipe = Pipeline(
                config,
                resident_pool=resident_pool,
                progress=lambda value, message: progress(value, desc=message),
            )
            pipe.config["target_language"] = "hi"
            job = pipe.prepare(video, runs)
            if read_json(job / "job.json").get("no_speech"):
                raise ValueError("No speech detected; use a clip with clear English speech.")
            segments = read_json(job / "segments.json")
            state = read_json(job / "job.json")
            yield (
                str(job),
                review_rows(segments),
                None,
                None,
                None,
                f"**Ready for review · {len(segments)} phrases · {state['duration']:.1f} s.** "
                "Check Hindi meaning, names and numbers, then confirm your review below.",
                gr.update(interactive=True),
                state,
                False,
            )
        except (ValueError, OSError, RuntimeError, KeyError) as exc:
            gr.Warning(str(exc))
            yield (
                "",
                [],
                None,
                None,
                None,
                "**Preparation stopped.** " + str(exc),
                gr.update(interactive=False),
                {},
                False,
            )

    def render(job, rows, consent, approved, mode, enhance_mouth=False, progress=gr.Progress()):
        yield (
            gr.skip(),
            gr.skip(),
            gr.skip(),
            "**Checking every speech slot before lip generation.** Long speech gets up to two faster-delivery retries with unchanged words, followed by a supported Hindi grammar contraction if needed (logged as AI-revised). Any previous successful result remains available below.",
            {},
        )
        try:
            if not consent:
                raise ValueError("Confirm permission to edit and dub this video.")
            if not job:
                raise ValueError("Prepare a video first.")
            if not approved:
                raise ValueError(
                    "Confirm that you checked the Hindi translation before generating."
                )
            folder = Path(job).resolve()
            if folder.parent != runs:
                raise ValueError("This job does not belong to the current studio.")
            state = read_json(folder / "job.json")
            segments = reviewed_segments(
                rows, read_json(folder / "segments.json"), state["duration"]
            )
            review = folder / "ui_review.json"
            write_json(review, segments)
            pipe = Pipeline(
                config,
                resident_pool=resident_pool,
                progress=lambda value, message: progress(value, desc=message),
            )
            pipe.config["overlap_tts"] = resident_pool is not None
            pipe.config["auto_compact_hindi"] = True
            pipe.config["rebalance_speech_timing"] = True
            if enhance_mouth:
                pipe.config["enhance_mouth"] = True
                pipe.config["commands"]["enhance"] = [
                    pipe.config["lipsync"]["python"],
                    str(Path(__file__).resolve().parents[1] / "adapters/enhance_gfpgan.py"),
                ]
            audio_only = mode == "Audio-only comparison"
            if mode == "LatentSync comparison · much slower":
                import sys

                pipe.config["commands"]["lipsync"] = [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "adapters/lipsync_latentsync.py"),
                ]
                pipe.config["lipsync"] = {}
                pipe.config["timeout_seconds"] = 7200
                pipe.config["enhance_mouth"] = False
            output = pipe.render(folder, review, audio_only)
            result = read_json(folder / "job.json")
            # Resolve immutable artifact paths so a later rerender cannot change an existing download.
            yield (
                str(output.resolve()),
                str((folder / "subtitles.srt").resolve()),
                str((folder / "delivery.zip").resolve()),
                f"**Complete · {'audio-only comparison' if audio_only else 'lip-synced Hindi'} · AI-dubbed.** "
                f"{result['output_seconds']:.1f} s video · {result['render_seconds']:.1f} s render. "
                "Watch and listen before sharing."
                + (
                    " AI shortened a Hindi phrase for timing; check the timing edits in Run details."
                    if result.get("automatic_timing_edits")
                    else ""
                )
                + (
                    " Phrase boundaries shifted by at most one second to fit speech; see Run details."
                    if result.get("timing_adjustments")
                    else ""
                ),
                result,
            )
        except (ValueError, OSError, RuntimeError, KeyError) as exc:
            gr.Warning(str(exc))
            yield (
                gr.skip(),
                gr.skip(),
                gr.skip(),
                "**No new video was generated.** "
                + str(exc)
                + " Edit the indicated Hindi phrase and approve it again. Any previous successful result is still playable.",
                {},
            )

    with gr.Blocks(
        title="Multilingua | Dubbing Studio", analytics_enabled=False, delete_cache=(3600, 86400)
    ) as app:
        gr.HTML("""<header id="masthead">
          <div class="eyebrow">MULTILINGUA / DUBBING STUDIO</div>
          <h1>Your ideas. A new language.</h1>
          <p>Turn English video into Hindi speech. Review every phrase,
          keep the timing, and bring the words to life with lip synchronization.</p>
          <div class="pills"><span class="pill">English → हिन्दी</span>
          <span class="pill">Human-reviewed translation</span>
          <span class="pill">Local processing</span></div></header>""")
        with gr.Tabs():
            with gr.Tab("Studio"):
                gr.HTML("""<div class="flow">
                  <div class="flow-item"><span class="step">1</span><div><b>Bring your video</b><small>Clear audio. One visible speaker.</small></div></div>
                  <div class="flow-item"><span class="step">2</span><div><b>Make the meaning right</b><small>Review and refine the Hindi.</small></div></div>
                  <div class="flow-item"><span class="step">3</span><div><b>Give it a new voice</b><small>Generate, compare and export.</small></div></div></div>""")
                setup_note = gr.Markdown(readiness_markdown(report), elem_id="setup-note")
                job = gr.State("")
                with gr.Row(equal_height=True):
                    with gr.Column():
                        gr.HTML('<div class="section-label">01 / ENGLISH SOURCE</div>')
                        source = gr.Video(
                            label="Original video",
                            sources=["upload", "webcam"],
                            format="mp4",
                            height=280,
                        )
                        gr.Markdown(
                            "Start with a **10–20 second** clip: one consenting adult, a frontal face, "
                            "and clear English speech. Maximum 10 minutes / 200 MB."
                        )
                    with gr.Column():
                        gr.HTML('<div class="section-label">03 / HINDI OUTPUT · AI-DUBBED</div>')
                        output = gr.Video(
                            label="Dubbed video · available after successful generation",
                            format="mp4",
                            interactive=False,
                            height=280,
                        )
                        gr.Markdown(
                            "The player stays empty until generation succeeds. Webcam records a clip; it is not live dubbing. The generated voice may differ from the speaker. "
                            "Audio-only mode keeps the original mouth movements."
                        )
                consent = gr.Checkbox(
                    label="I have permission to process this video, edit the speaker’s likeness, and use any reference voice."
                )
                prep = gr.Button("Transcribe & translate →", variant="primary", size="lg")
                status = gr.Markdown(
                    "**Start here.** Upload a video and confirm permission to begin.",
                    elem_id="status",
                )
                gr.HTML('<div class="section-label">02 / REVIEW THE TRANSLATION</div>')
                gr.Markdown(
                    "Edit the **Hindi translation** column. Keep names, numbers and meaning intact. "
                    "Short, natural phrases are easier to fit to the original timing. On small screens, scroll the table sideways."
                )
                review = gr.Dataframe(
                    headers=[
                        "#",
                        "Start (s)",
                        "End (s)",
                        "English transcript",
                        "Hindi translation",
                    ],
                    datatype=["number", "number", "number", "str", "str"],
                    type="array",
                    value=[],
                    interactive=True,
                    static_columns=[0, 1, 2, 3],
                    column_count=5,
                    row_count=0,
                    wrap=True,
                    max_height=360,
                    column_widths=["6%", "10%", "10%", "37%", "37%"],
                    label="Phrase-by-phrase review",
                    elem_id="review-table",
                )
                approved = gr.Checkbox(
                    label="I checked the Hindi translation for meaning, names and numbers."
                )
                with gr.Row():
                    mode = gr.Radio(
                        [
                            "Lip-synced Hindi",
                            "LatentSync comparison · much slower",
                            "Audio-only comparison",
                        ],
                        value="Lip-synced Hindi",
                        label="Output mode",
                        info="Lip-synced Hindi uses MuseTalk. LatentSync generates another lip result, takes much longer, and skips GFPGAN. Natural appearance is not guaranteed.",
                    )
                    render_button = gr.Button(
                        "Generate dubbed video →", variant="primary", interactive=False, size="lg"
                    )
                enhance_mouth = gr.Checkbox(
                    value=False,
                    label="GFPGAN mouth enhancement · experimental, slower",
                    info="OFF recommended for natural appearance. May invent teeth or alter lip shape; sharper does not mean more realistic. MuseTalk only; adds roughly 0.1 seconds per frame.",
                )
                with gr.Row():
                    captions = gr.File(label="Hindi subtitles · SRT", interactive=False, height=110)
                    bundle = gr.File(
                        label="Delivery · video, subtitles & review record",
                        interactive=False,
                        height=110,
                    )
                with gr.Accordion("Run details", open=False):
                    details = gr.JSON(label="Measured timings and job status")
                    gr.Markdown(
                        "Render time includes model loading. It is not live streaming latency. "
                        "Jobs and logs stay in your local runs folder until you delete them."
                    )
            with gr.Tab("Saved results"):
                gr.Markdown(
                    "Completed videos stay here after refreshing. Select a result to compare the original and dub. AI-revised translations still need human review."
                )
                saved = gr.Dropdown(label="Completed job", choices=[], interactive=True)
                refresh_saved = gr.Button("Refresh completed videos")
                with gr.Row():
                    saved_source = gr.Video(label="Saved original", interactive=False, format="mp4")
                    saved_output = gr.Video(
                        label="Saved dubbed video", interactive=False, format="mp4"
                    )
                saved_bundle = gr.File(label="Download delivery ZIP", interactive=False)

                def completed_jobs():
                    jobs = sorted(
                        (p.parent for p in runs.glob("*/output.mp4")),
                        key=lambda p: (p / "output.mp4").stat().st_mtime,
                        reverse=True,
                    )
                    choices = []
                    for folder in jobs[:30]:
                        metadata = (
                            read_json(folder / "job.json") if (folder / "job.json").exists() else {}
                        )
                        mode = "Lip-synced" if metadata.get("lip_sync") else "Audio-only"
                        seconds = metadata.get("output_seconds", metadata.get("duration", 0))
                        choices.append(
                            (f"{mode} · {seconds:.1f}s · {folder.name[:8]}", folder.name)
                        )
                    return gr.update(choices=choices, value=None)

                def show_saved(name):
                    if not name:
                        return None, None, None
                    folder = (runs / name).resolve()
                    if folder.parent != runs or not (folder / "output.mp4").is_file():
                        raise gr.Error("Unknown completed job")

                    def artifact(filename):
                        p = folder / filename
                        return str(p.resolve()) if p.is_file() else None

                    return artifact("source.mp4"), artifact("output.mp4"), artifact("delivery.zip")

                app.load(completed_jobs, [], [saved])
                refresh_saved.click(completed_jobs, [], [saved])
                saved.change(show_saved, [saved], [saved_source, saved_output, saved_bundle])
            with gr.Tab("How it works"):
                gr.Markdown("""## From a spoken idea to a reviewed dub

**Recognize → Translate → Review → Speak → Fit → Synchronize → Export**

1. **Recognize.** Whisper converts English audio into timestamped phrases.
2. **Translate.** IndicTrans2 produces Hindi text. You correct meaning before speech is generated.
3. **Speak.** Indic Parler-TTS generates a generic Hindi voice; an optional IndicF5 adapter uses a permitted reference voice.
4. **Fit.** Short speech is padded with silence. Speech up to 25% too long is gently accelerated. Longer speech stops for a shorter translation.
5. **Synchronize.** MuseTalk edits mouth regions using the fitted speech. Audio-only mode skips this step explicitly.
6. **Export.** Download video, Hindi subtitles, timing measurements and an AI-dubbed disclosure together.

### Choose a clip that works well
Use a single frontal speaker without cuts, overlapping voices, music or heavy background noise.
The current release replaces background audio with silence outside speech. It processes recorded
video; webcam calls, arbitrary languages and real-time playback are outside this release.

### You stay in control
Models can mistranscribe speech, change meaning, mispronounce a name, or create mouth artifacts.
Review text, listen to the speech, and watch the full output. Do not treat model output as a faithful
record of what someone originally said. Label any shared clip as AI-dubbed.

**Privacy:** inference uses local adapters. Initial model setup contacts model hosts to download weights.
Uploads and outputs remain on disk. This studio is intended for one trusted local operator.
""")
            with gr.Tab("System check"):
                gr.Markdown(
                    "## Prepare the workstation\nCopy `configs/local.example.json` to `configs/local.json`, "
                    "then set your Python environments and model paths. See **docs/SETUP.md** in the repository. "
                    "Checks below do not download or run models."
                )
                checks = gr.Dataframe(
                    headers=["Check", "Status", "Details"],
                    value=[
                        [
                            c["name"],
                            "OK" if c["ok"] else ("Missing" if c["required"] else "Optional"),
                            c["detail"],
                        ]
                        for c in report["checks"]
                    ],
                    interactive=False,
                    wrap=True,
                    label="Local dependency readiness",
                )
                refresh = gr.Button("Refresh system check")
                gr.Markdown(
                    "A successful check validates local paths only. Rehearse all model stages with a permitted "
                    "clip before presenting. Model access and auxiliary weights still need verification."
                )
        gr.HTML(
            '<div id="footer">Multilingua · English–Hindi recorded-video research prototype · Review before sharing</div>'
        )
        shared = {"concurrency_id": "model-work", "concurrency_limit": 1}
        prep.click(
            prepare,
            [source, consent],
            [job, review, output, captions, bundle, status, render_button, details, approved],
            **shared,
        )
        render_button.click(
            render,
            [job, review, consent, approved, mode, enhance_mouth],
            [output, captions, bundle, status, details],
            **shared,
        )

        def reset_source():
            return (
                "",
                [],
                None,
                None,
                None,
                False,
                False,
                gr.update(interactive=False),
                "**New source.** Confirm permission, then transcribe and translate.",
                {},
            )

        source.change(
            reset_source,
            [],
            [
                job,
                review,
                output,
                captions,
                bundle,
                consent,
                approved,
                render_button,
                status,
                details,
            ],
            **shared,
        )
        review.input(lambda: False, [], [approved], **shared)

        def refresh_checks():
            latest = diagnose(config)
            return (
                [
                    [
                        c["name"],
                        "OK" if c["ok"] else ("Missing" if c["required"] else "Optional"),
                        c["detail"],
                    ]
                    for c in latest["checks"]
                ],
                readiness_markdown(latest),
            )

        refresh.click(refresh_checks, [], [checks, setup_note])
    return app


def launch(config, runs="runs", port=7860):
    import atexit
    import signal

    import gradio as gr

    from .resident import ResidentPool

    pool = ResidentPool(Path(runs) / "studio-worker-logs")
    atexit.register(pool.close)

    def shutdown_studio(signum, frame):
        # SIGTERM otherwise bypasses atexit and leaves GPU workers running.
        pool.close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutdown_studio)
    app = build_app(config, runs, resident_pool=pool)
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="slate",
        neutral_hue="slate",
        font=["ui-sans-serif", "system-ui", "sans-serif"],
    )
    app.queue(default_concurrency_limit=1, max_size=8).launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        max_file_size="200mb",
        theme=theme,
        css=CSS,
        footer_links=[],
    )
