import argparse
import base64
import json
import hashlib
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--reference', action='append', default=[])
parser.add_argument('--speaker')
parser.add_argument('--format', default='mp3')
args = parser.parse_args()
key = os.environ.get('SEED_AUDIO_API_KEY') or sys.stdin.readline().strip()
if not key:
    raise SystemExit('Missing API key')
body = {
    'model': 'seed-audio-1.0',
    'text_prompt': Path(args.prompt).read_text(),
    'audio_config': {'format': args.format, 'sample_rate': 24000, 'enable_subtitle': True},
}
if args.reference:
    if args.speaker or len(args.reference) > 3:
        raise SystemExit('Use up to three reference audio files, without --speaker')
    body['references'] = []
    for reference in args.reference:
        data = Path(reference).read_bytes()
        if len(data) > 10 * 1024 * 1024:
            raise SystemExit('Reference exceeds 10 MB')
        body['references'].append({'audio_data': base64.b64encode(data).decode()})
elif args.speaker:
    body['references'] = [{'speaker': args.speaker}]
request_id = str(uuid.uuid4())
request = urllib.request.Request(
    'https://openspeech.bytedance.com/api/v3/tts/create',
    data=json.dumps(body).encode(),
    headers={'Content-Type': 'application/json', 'X-Api-Key': key, 'X-Api-Request-Id': request_id},
)
start = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.load(response)
        status = response.status
        logid = response.headers.get('X-Tt-Logid')
except urllib.error.HTTPError as exc:
    print('HTTP', exc.code, exc.read().decode()[:2000].replace(key, '[REDACTED]'))
    raise SystemExit(1)
except Exception as exc:
    print(type(exc).__name__, str(exc).replace(key, '[REDACTED]'))
    raise SystemExit(1)
if not result.get('audio'):
    print(json.dumps(result, ensure_ascii=False)[:2000].replace(key, '[REDACTED]'))
    raise SystemExit(1)
output = Path(args.output)
output.write_bytes(base64.b64decode(result['audio'], validate=True))
metadata = {k: v for k, v in result.items() if k not in ('audio', 'url')}
metadata.update(http_status=status, request_id=request_id, logid=logid,
                elapsed_seconds=round(time.monotonic()-start, 2), bytes=output.stat().st_size)
metadata['model'] = body['model']
metadata['reference_files'] = [{'marker': '@音频'+str(i), 'path': str(Path(p).resolve()), 'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()} for i,p in enumerate(args.reference, 1)]
metadata['speaker'] = args.speaker
output.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
print(json.dumps({k:v for k,v in metadata.items() if k != 'subtitle'}, ensure_ascii=False))
print(metadata.get('subtitle', {}).get('text', ''))
