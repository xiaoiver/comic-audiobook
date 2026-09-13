#!/usr/bin/env python3
"""Seed Audio WAV generation with immutable outputs and credential-free previews."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
import uuid
import wave

ENDPOINT = 'https://openspeech.bytedance.com/api/v3/tts/create'


def make_request(prompt_path, references=(), image=None, speaker=None, model='seed-audio-1.0'):
    prompt = Path(prompt_path).read_text(encoding='utf-8')
    if not prompt.strip():
        raise ValueError('Empty prompt')
    if sum([bool(references), bool(image), bool(speaker)]) > 1:
        raise ValueError('Use audio references, one image, or a speaker; do not mix modes')
    if len(references) > 3:
        raise ValueError('This adapter supports up to three audio references; verify current API limits')
    body = {'model': model, 'text_prompt': prompt,
            'audio_config': {'format': 'wav', 'sample_rate': 24000, 'enable_subtitle': True}}
    review = {'endpoint': ENDPOINT, 'model': model, 'text_prompt': prompt,
              'audio_config': body['audio_config'], 'references': []}
    entries = []
    for i, value in enumerate(references, 1):
        p = Path(value).resolve(); data = p.read_bytes()
        if not data or len(data) > 10 * 1024 * 1024:
            raise ValueError(f'Invalid reference size: {p.name}')
        # WAV-only helper keeps duration validation deterministic and offline.
        with wave.open(str(p)) as w:
            duration = w.getnframes() / w.getframerate()
        if not 0 < duration <= 30:
            raise ValueError(f'Reference duration outside (0, 30] seconds: {p.name}')
        entries.append({'audio_data': base64.b64encode(data).decode()})
        review['references'].append({'marker': f'@音频{i}', 'path': str(p),
            'sha256': hashlib.sha256(data).hexdigest(), 'duration_seconds': duration})
    markers = {int(x) for x in re.findall(r'@音频(\d+)', prompt)}
    if markers != set(range(1, len(references) + 1)):
        raise ValueError('Prompt markers must exactly match the supplied audio reference order')
    if image:
        p = Path(image).resolve(); data = p.read_bytes()
        supported = data.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')) or (
            data.startswith(b'RIFF') and data[8:12] == b'WEBP')
        if not supported or len(data) > 10 * 1024 * 1024:
            raise ValueError('Image must be JPEG, PNG or WebP, at most 10 MB')
        entries = [{'image_data': base64.b64encode(data).decode()}]
        review['references'] = [{'image_path': str(p), 'sha256': hashlib.sha256(data).hexdigest()}]
    if speaker:
        entries = [{'speaker': speaker}]; review['references'] = entries
    if entries:
        body['references'] = entries
    return body, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reference', action='append', default=[], type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--speaker')
    parser.add_argument('--model', default='seed-audio-1.0')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--key-stdin', action='store_true')
    args = parser.parse_args()
    body, review = make_request(args.prompt, args.reference, args.image, args.speaker, args.model)
    if args.output.suffix.lower() != '.wav':
        raise ValueError('Output must have a .wav extension')
    if args.dry_run:
        print(json.dumps(review, ensure_ascii=False, indent=2)); return
    targets = [args.output, args.output.with_suffix('.json'), args.output.with_suffix('.request.json')]
    if any(p.exists() for p in targets):
        raise FileExistsError('Output version already exists; choose a new output name')
    key = os.environ.get('SEED_AUDIO_API_KEY')
    if not key:
        key = sys.stdin.readline().strip() if args.key_stdin else (
            getpass.getpass('Seed API Key: ') if sys.stdin.isatty() else '')
    if not key:
        raise ValueError('Set SEED_AUDIO_API_KEY or provide --key-stdin')
    request_id = str(uuid.uuid4()); review['request_id'] = request_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    targets[2].write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={
        'Content-Type': 'application/json', 'X-Api-Key': key, 'X-Api-Request-Id': request_id})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response); logid = response.headers.get('X-Tt-Logid')
        if not isinstance(result.get('audio'), str) or not result['audio']:
            raise ValueError('API returned no audio; inspect request ID before another paid attempt')
        data = base64.b64decode(result['audio'], validate=True)
        # Validate the audio before publishing the output file.
        import io
        with wave.open(io.BytesIO(data)) as w:
            duration = w.getnframes() / w.getframerate()
        if duration <= 0:
            raise ValueError('Empty WAV output')
        with args.output.open('xb') as f:
            f.write(data)
        metadata = {k: result[k] for k in ('duration', 'original_duration', 'subtitle') if k in result}
        metadata.update(request_id=request_id, logid=logid, model=args.model,
                        reference_files=review['references'], measured_duration_seconds=duration,
                        elapsed_seconds=round(time.monotonic() - start, 2),
                        audio_sha256=hashlib.sha256(data).hexdigest())
        targets[1].write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'output': str(args.output.resolve()), 'request_id': request_id,
                          'duration_seconds': duration}, ensure_ascii=False))
    except Exception as exc:
        message = str(exc).replace(key, '[REDACTED]')[:1500]
        args.output.with_suffix('.error.json').write_text(json.dumps({
            'request_id': request_id, 'error': message, 'automatic_retry': False,
            'billing_outcome_may_be_unknown': True}, ensure_ascii=False, indent=2), encoding='utf-8')
        raise RuntimeError(message) from None


if __name__ == '__main__':
    main()
