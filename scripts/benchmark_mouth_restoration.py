"""Experimental GFPGAN full-face restoration, composited only around the mouth.
Uses existing dubbed video/audio. No claim of improved phonetic alignment.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/restoration-deps"))
import cv2
import numpy as np
import torch
from gfpgan import GFPGANer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--strength", type=float, default=0.65)
    p.add_argument("--temporal", type=float, default=0)
    p.add_argument("--colour", action="store_true")
    p.add_argument(
        "--efficient", action="store_true", help="Detect at 640px and warp only the mouth ROI"
    )
    args = p.parse_args()
    if not 0 <= args.strength <= 1 or not 0 <= args.temporal <= 0.15:
        raise ValueError("Strength must be 0–1 and temporal weight 0–0.15")
    source = args.input.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = ROOT / "models/restoration/GFPGANv1.4.pth"
    os.chdir(ROOT / "models/restoration")
    torch.set_num_threads(4)
    start = time.perf_counter()
    restorer = GFPGANer(
        model_path=str(model),
        upscale=1,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=None,
        device=torch.device("cuda"),
    )
    if args.efficient:
        original_detect = restorer.face_helper.get_face_landmarks_5

        def detect(**kwargs):
            return original_detect(resize=640, **kwargs)

        restorer.face_helper.get_face_landmarks_5 = detect
    torch.cuda.synchronize()
    load = time.perf_counter() - start
    cap = cv2.VideoCapture(str(source))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(3))
    h = int(cap.get(4))
    silent = output.with_suffix(".silent.mp4")
    encoder = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{w}x{h}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(silent),
        ],
        stdin=subprocess.PIPE,
    )
    rows = []
    previous = None
    misses = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            torch.cuda.synchronize()
            began = time.perf_counter()
            with torch.inference_mode():
                _, faces, restored = restorer.enhance(
                    frame,
                    has_aligned=False,
                    only_center_face=True,
                    paste_back=not args.efficient,
                    weight=0.5,
                )
                if args.efficient:
                    restored = faces[0] if len(faces) == 1 else None
            torch.cuda.synchronize()
            restoration = time.perf_counter() - began
            points = restorer.face_helper.all_landmarks_5
            result = frame.copy()
            sharpness = {}
            if restored is None or len(points) != 1:
                misses += 1
                previous = None
            else:
                mouth = np.asarray(points[0][3:5])
                center = mouth.mean(axis=0)
                width = float(np.linalg.norm(mouth[1] - mouth[0]))
                rx = max(4, int(width * 0.8))
                ry = max(3, int(width * 0.48))
                x0 = max(0, int(center[0]) - rx - 12)
                x1 = min(w, int(center[0]) + rx + 13)
                y0 = max(0, int(center[1]) - ry - 12)
                y1 = min(h, int(center[1]) + ry + 13)
                base = frame[y0:y1, x0:x1].astype(np.float32)
                if args.efficient:
                    inverse = cv2.invertAffineTransform(restorer.face_helper.affine_matrices[0])
                    inverse[:, 2] -= np.array([x0, y0])
                    detail = cv2.warpAffine(
                        restored, inverse, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR
                    ).astype(np.float32)
                else:
                    detail = restored[y0:y1, x0:x1].astype(np.float32)
                mask = np.zeros(base.shape[:2], np.float32)
                angle = float(np.degrees(np.arctan2(*(mouth[1] - mouth[0])[::-1])))
                cv2.ellipse(
                    mask, (int(center[0]) - x0, int(center[1]) - y0), (rx, ry), angle, 0, 360, 1, -1
                )
                mask = cv2.GaussianBlur(mask, (0, 0), 3)
                if args.colour:
                    # Match surrounding colour, not the teeth or mouth cavity.
                    ring = (mask > 0.05) & (mask < 0.3)
                    if ring.sum() > 30:
                        shift = np.clip(
                            np.median(base[ring], axis=0) - np.median(detail[ring], axis=0), -10, 10
                        )
                        detail = np.clip(detail + shift, 0, 255)
                if args.temporal and previous is not None:
                    prior = cv2.resize(previous, (detail.shape[1], detail.shape[0]))
                    # Suppress smoothing on rapid mouth changes to limit ghosting.
                    gate = np.clip(1 - np.mean(np.abs(detail - prior), axis=2) / 15, 0, 1)
                    alpha = (args.temporal * gate)[..., None]
                    detail = detail * (1 - alpha) + prior * alpha
                previous = detail.copy()
                alpha = (mask * args.strength)[..., None]
                result[y0:y1, x0:x1] = np.clip(base * (1 - alpha) + detail * alpha, 0, 255).astype(
                    np.uint8
                )
                core = mask > 0.8
                if core.sum() > 20:
                    for key, patch in [("baseline", base), ("enhanced", result[y0:y1, x0:x1])]:
                        gray = cv2.cvtColor(patch.astype(np.uint8), cv2.COLOR_BGR2GRAY)
                        sharpness[key + "_mouth_laplacian_variance"] = float(
                            cv2.Laplacian(gray, cv2.CV_32F)[core].var()
                        )
            elapsed = time.perf_counter() - began
            encoder.stdin.write(np.ascontiguousarray(result).tobytes())
            rows.append(
                {"restoration_ms": restoration * 1000, "total_ms": elapsed * 1000, **sharpness}
            )
            if len(rows) % 25 == 0:
                print("frames", len(rows), flush=True)
    finally:
        cap.release()
        encoder.stdin.close()
        encoder.wait()
    if encoder.returncode or not rows:
        raise RuntimeError("Video encoding failed or input empty")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(silent),
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )
    report = {
        "input": str(source),
        "output": str(output),
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "frames": len(rows),
        "fps": fps,
        "load_seconds": load,
        "missed_faces": misses,
        "settings": {
            "strength": args.strength,
            "temporal": args.temporal,
            "colour": args.colour,
            "efficient": args.efficient,
        },
        "mean_ms_per_frame": float(np.mean([r["total_ms"] for r in rows])),
        "mean_restoration_ms": float(np.mean([r["restoration_ms"] for r in rows])),
        "peak_torch_bytes": torch.cuda.max_memory_allocated(),
        "frames_timing": rows,
        "note": "Whole aligned face restored; only feathered mouth pasted. Timings exclude video encode/mux. Quality and sync must be evaluated separately.",
    }
    output.with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "frames_timing"}), flush=True)


if __name__ == "__main__":
    main()
