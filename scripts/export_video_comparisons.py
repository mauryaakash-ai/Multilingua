"""Export completed experiments as original-then-dubbed review videos."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe(p):
    return json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)]
        )
    )


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    pairs = []

    def add(name, source, dub, note="", duration=None):
        source = ROOT / source
        dub = ROOT / dub
        if source.is_file() and dub.is_file():
            pairs.append((name, source, dub, note, duration))

    for base in [
        "runs/server",
        "runs/multispeaker",
        "runs/profiling/integrated/jobs",
        "runs/profiling/integrated-fp16/jobs",
    ]:
        for dub in sorted((ROOT / base).glob("*/output.mp4")):
            source = dub.parent / ("input.mp4" if base == "runs/server" else "source.mp4")
            label = base.replace("runs/", "").replace("/", "-") + "-" + dub.parent.name[:8]
            add(label, source, dub)
    add(
        "hdtf-original-voice-demo",
        "runs/hdtf-audio-demo/source.mp4",
        "runs/hdtf-audio-demo/output.mp4",
        "Audio dubbing baseline; lips may be unchanged.",
    )
    for name in ["audio-only", "lipsynced"]:
        add(
            "hdtf-rohit-" + name,
            "runs/hdtf-first/source.mp4",
            f"runs/hdtf-male-demo/{name}.mp4",
            "Audio-only baseline." if name == "audio-only" else "",
        )
    add(
        "service-evaluation",
        "runs/evaluation/service-input.mp4",
        "runs/evaluation/service-output.mp4",
    )
    source = next((ROOT / "runs/server/1364107fbec84529bdf167a587965469/work").glob("*/source.mp4"))
    for name in [
        "full-precision",
        "improved",
        "output-improved",
        "musetalk-preview",
        "latentsync-preview-trimmed",
    ]:
        dub = ROOT / f"runs/lip-quality/{name}.mp4"
        if dub.exists():
            add(
                "lip-quality-" + name, source, dub, duration=float(probe(dub)["format"]["duration"])
            )
    for dub in sorted((ROOT / "runs/evaluation/latentsync-grid").glob("*-trimmed.mp4")):
        add(
            "latentsync-" + dub.stem,
            source,
            dub,
            "Experimental faster preset; alignment scores worse than quality baseline.",
            2.4,
        )
    source5 = ROOT / "runs/evaluation/service-input.mp4"
    add("resident-musetalk-test", source5, "runs/profiling/resident/lips.mp4")
    # Downloads may be an exact copy of a completed job. Include only if provenance matches.
    download = Path("/home/akash/Downloads/output.mp4")
    if download.exists():
        h = digest(download)
        for _, src, dub, note, duration in list(pairs):
            if digest(dub) == h:
                add("downloaded-output", src, download, note, duration)
                break
    seen = {}
    rows = []
    duplicates = []
    with tempfile.TemporaryDirectory(prefix="video-review-") as tmp:
        for name, src, dub, note, limit in pairs:
            h = digest(dub)
            if h in seen:
                duplicates.append({"path": str(dub), "same_as": seen[h]})
                continue
            seen[h] = name
            ds = probe(src)
            dd = probe(dub)
            v = next(s for s in ds["streams"] if s["codec_type"] == "video")
            w = v["width"] // 2 * 2
            he = v["height"] // 2 * 2
            original_seconds = (
                min(float(ds["format"]["duration"]), limit)
                if limit
                else float(ds["format"]["duration"])
            )
            target = a.output / (name + ".mp4")
            parts = []
            for i, (p, meta, seconds, label) in enumerate(
                [
                    (src, ds, original_seconds, "ORIGINAL"),
                    (dub, dd, float(dd["format"]["duration"]), "DUBBED - AI edited"),
                ]
            ):
                part = Path(tmp) / f"{i}.mp4"
                parts.append(part)
                cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(p)]
                has_audio = any(s["codec_type"] == "audio" for s in meta["streams"])
                if not has_audio:
                    cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                vf = f"scale={w}:{he}:force_original_aspect_ratio=decrease,pad={w}:{he}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{label}':x=12:y=12:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6"
                cmd += [
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0" if has_audio else "1:a:0",
                    "-vf",
                    vf,
                    "-af",
                    "apad",
                    "-t",
                    str(seconds),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "18",
                    "-threads",
                    "4",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    str(part),
                ]
                subprocess.run(cmd, check=True)
            listing = Path(tmp) / "concat.txt"
            listing.write_text("".join(f"file '{p}'\n" for p in parts))
            pending = target.with_suffix(".pending.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(listing),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(pending),
                ],
                check=True,
            )
            actual = float(probe(pending)["format"]["duration"])
            expected = original_seconds + float(dd["format"]["duration"])
            if abs(actual - expected) > 0.3:
                raise RuntimeError(f"Duration mismatch: {name} {actual} vs {expected}")
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(pending), "-f", "null", "-"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            pending.replace(target)
            rows.append(
                {
                    "file": target.name,
                    "original": str(src),
                    "dubbed": str(dub),
                    "dubbed_sha256": h,
                    "original_seconds": original_seconds,
                    "switch_seconds": float(probe(parts[0])["format"]["duration"]),
                    "total_seconds": actual,
                    "note": note,
                }
            )
            (a.output / "manifest.json").write_text(
                json.dumps({"videos": rows, "duplicate_copies_skipped": duplicates}, indent=2)
            )
            print(f"Saved {target.name} ({actual:.2f}s)", flush=True)
    (a.output / "README.txt").write_text(
        "Original then dubbed comparison videos\n\nEach MP4 plays the original first, then the AI-edited dubbed result, with labels and audio.\nOnly completed outputs are included; exact duplicate copies are skipped.\nmanifest.json records sources, switch times and test limitations.\n\n"
        + "\n".join(
            f"{r['file']} | dubbed starts {r['switch_seconds']:.2f}s | {r['note']}" for r in rows
        )
    )
    print(
        f"COMPLETE: {len(rows)} comparisons; {len(duplicates)} duplicate copies skipped", flush=True
    )


if __name__ == "__main__":
    main()
