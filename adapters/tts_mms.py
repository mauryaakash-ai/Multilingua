"""Synthesize Hindi speech locally with the MMS Hindi VITS checkpoint."""

import argparse
import json
import wave
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request["language"] != "hi":
        raise ValueError("This voice checkpoint supports Hindi only.")
    import numpy as np
    import torch
    from transformers import AutoTokenizer, VitsModel

    torch.set_num_threads(4)
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(request["model"])
    model = VitsModel.from_pretrained(request["model"]).eval()
    inputs = tokenizer(request["text"], return_tensors="pt")
    with torch.inference_mode():
        samples = model(**inputs).waveform[0].cpu().numpy()
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise ValueError("Speech model returned invalid samples.")
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(request["output"], "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(model.config.sampling_rate)
        output.writeframes(pcm.tobytes())
    args.response.write_text(json.dumps({"audio": request["output"]}), encoding="utf-8")


if __name__ == "__main__":
    main()
