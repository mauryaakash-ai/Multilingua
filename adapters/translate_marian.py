"""English-to-Hindi OPUS-MT using an explicitly selected Marian checkpoint."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if (request["source"], request["target"]) != ("eng_Latn", "hin_Deva"):
        raise ValueError("This checkpoint translates English to Hindi.")
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    torch.set_num_threads(4)
    tokenizer = MarianTokenizer.from_pretrained(args.model)
    model = MarianMTModel.from_pretrained(args.model).eval()
    translations = []
    texts = request["texts"]
    for offset in range(0, len(texts), 8):
        inputs = tokenizer(texts[offset : offset + 8], padding=True, return_tensors="pt")
        if inputs.input_ids.shape[1] > tokenizer.model_max_length:
            raise ValueError("A phrase exceeds the translation model's input limit.")
        with torch.inference_mode():
            output = model.generate(**inputs, num_beams=4, max_new_tokens=384)
        translations.extend(tokenizer.batch_decode(output, skip_special_tokens=True))
    args.response.write_text(
        json.dumps({"texts": translations}, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
