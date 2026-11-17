"""Local English-to-Spanish NLLB adapter; no remote inference fallback."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--response', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text())
    if request.get('source') != 'eng_Latn' or request.get('target') != 'spa_Latn':
        raise ValueError('This adapter supports English to Spanish only')
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(args.model, src_lang='eng_Latn', local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model, local_files_only=True).to(args.device).eval()
    results = []
    for text in request['texts']:
        tokens = tokenizer(text, return_tensors='pt').to(args.device)
        if tokens.input_ids.shape[-1] > 512:
            raise ValueError('Phrase exceeds NLLB context; split it before translation')
        with torch.inference_mode():
            translated = model.generate(**tokens, forced_bos_token_id=tokenizer.convert_tokens_to_ids('spa_Latn'), max_new_tokens=512)
        results.append(tokenizer.batch_decode(translated, skip_special_tokens=True)[0])
    Path(args.response).write_text(json.dumps({'texts': results}, ensure_ascii=False))


if __name__ == '__main__':
    main()
