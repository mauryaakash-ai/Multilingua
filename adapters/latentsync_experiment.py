"""Isolated 512px LatentSync experiment; not enabled in the live application.

Uses the official 1.6 checkpoint with smaller temporal batches and VAE slicing
for this 16 GB GPU. Reduced temporal context requires visual validation.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--guidance", type=float, default=1.5)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    repo = root / "vendor/LatentSync"
    output = Path(a.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="latentsync_") as tmp:
        work = Path(tmp)
        shutil.copyfile(a.video, work / "video.mp4")
        shutil.copyfile(a.audio, work / "audio.wav")
        runner = work / "run.py"
        runner.write_text("""import sys,torch,os
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import insightface.app
import onnxruntime as ort
original_face=insightface.app.FaceAnalysis
class CPUFaceAnalysis(original_face):
    def __init__(self,*a,**kw):
        kw["providers"]=["CPUExecutionProvider"]
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        kw["sess_options"]=options
        super().__init__(*a,**kw)
insightface.app.FaceAnalysis=CPUFaceAnalysis
from scripts import inference
import numpy as np, subprocess
import latentsync.pipelines.lipsync_pipeline as pipeline_module
def write_video(path, frames, fps=25):
    # Keep generated frames outside temporary staging until encoding succeeds.
    np.save(sys.argv[7],frames)
    h,w=frames.shape[1:3]
    cmd=["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{w}x{h}","-r",str(fps),"-i","-","-an","-c:v","libx264","-crf","18","-pix_fmt","yuv420p",str(path)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
        for frame in frames:process.stdin.write(np.ascontiguousarray(frame).tobytes())
        process.stdin.close()
        if process.wait():raise RuntimeError("FFmpeg frame encoding failed; generated frames retained")
pipeline_module.write_video=write_video
from omegaconf import OmegaConf
from types import SimpleNamespace
original=inference.AutoencoderKL.from_pretrained
inference.AutoencoderKL.from_pretrained=lambda *a,**kw: original(os.environ.get('MULTILINGUA_VAE', str(Path.home()/'MuseTalk/models/sd-vae')),**kw)
original_to=inference.LipsyncPipeline.to
def memory_to(self,*a,**kw):
    result=original_to(self,*a,**kw)
    self.enable_vae_slicing()
    return result
inference.LipsyncPipeline.to=memory_to
torch.set_num_threads(4)
c=OmegaConf.load('configs/unet/stage2_512.yaml')
c.data.num_frames=int(sys.argv[1])
a=SimpleNamespace(video_path=sys.argv[2],audio_path=sys.argv[3],video_out_path=sys.argv[4],inference_ckpt_path='checkpoints/latentsync_unet.pt',inference_steps=int(sys.argv[5]),guidance_scale=float(sys.argv[8]),temp_dir=sys.argv[6],seed=1247,enable_deepcache=False)
inference.main(c,a)
print('PEAK_GPU_BYTES',torch.cuda.max_memory_allocated())
""")
        start = time.monotonic()
        with output.with_suffix(".log").open("w") as log:
            subprocess.run(
                [
                    str(root / ".venv-latentsync/bin/python"),
                    str(runner),
                    str(a.frames),
                    str(work / "video.mp4"),
                    str(work / "audio.wav"),
                    str(work / "output.mp4"),
                    str(a.steps),
                    str(work / "temp"),
                    str(output.with_suffix(".frames.npy")),
                    str(a.guidance),
                ],
                cwd=repo,
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if not (work / "output.mp4").is_file():
            raise RuntimeError("No output produced")
        shutil.copyfile(work / "output.mp4", output)
        output.with_suffix(".json").write_text(
            json.dumps(
                {
                    "seconds": time.monotonic() - start,
                    "frames_per_batch": a.frames,
                    "steps": a.steps,
                    "guidance": a.guidance,
                    "resolution": 512,
                    "seed": 1247,
                    "validated_quality": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
