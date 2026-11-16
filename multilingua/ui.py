"""Optional local research UI. Not a hosted multi-user service."""
import json
from pathlib import Path
from .pipeline import Pipeline, read_json, write_json

def launch(config):
    import gradio as gr
    pipe = Pipeline(config)
    def prepare(video):
        if not video:
            raise gr.Error('Upload a video first')
        job = pipe.prepare(video)
        return str(job), json.dumps(read_json(job/'segments.json'), ensure_ascii=False, indent=2), 'Ready for translation review'
    def render(job, text, consent, audio_only):
        if not consent:
            raise gr.Error('Confirm permission to edit and dub this video')
        if not job:
            raise gr.Error('Prepare a video first')
        review = Path(job)/'ui_review.json'
        write_json(review, json.loads(text))
        output = pipe.render(job, review, audio_only)
        return str(output), str(Path(job)/'subtitles.srt'), json.dumps(read_json(Path(job)/'job.json'),indent=2)
    with gr.Blocks(title='Multilingua • Dubbing Lab') as app:
        gr.Markdown('# Multilingua Dubbing Lab\nEnglish → Hindi · Recorded-video prototype')
        gr.Markdown('Review the translation before generating speech. Live webcam translation is a later milestone.')
        job = gr.State('')
        with gr.Row():
            source = gr.Video(label='English source video', sources=['upload'])
            output = gr.Video(label='Translated output')
        prep = gr.Button('1. Transcribe and translate', variant='primary')
        review = gr.Textbox(label='2. Review segment translations (JSON; preserve timestamps)', lines=14)
        consent = gr.Checkbox(label='I have permission to edit and dub this video')
        audio_only = gr.Checkbox(label='Audio-only comparison (no lip editing)', value=False)
        render_button = gr.Button('3. Generate dubbed video', variant='primary')
        captions = gr.File(label='Subtitles')
        status = gr.Textbox(label='Job status and measurements', lines=8)
        prep.click(prepare, [source], [job,review,status])
        render_button.click(render,[job,review,consent,audio_only],[output,captions,status])
    app.queue(default_concurrency_limit=1).launch(server_name='127.0.0.1',share=False)
