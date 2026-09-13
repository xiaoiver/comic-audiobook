"""MiniMax ASR: retain word/character timing and anonymous speaker IDs.

Requires MINIMAX_API_KEY. No GID parameter is documented for this endpoint.
https://platform.minimax.io/docs/api-reference/speech-to-text
"""

import argparse
import json
import math
import mimetypes
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid
import wave


def multipart(path):
    boundary = 'minimax-' + uuid.uuid4().hex
    chunks = []
    fields = {'model': 'asr-1.0', 'response_format': 'verbose_json',
              'timestamp_level': 'word', 'stream': 'false'}
    for name, value in fields.items():
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; '
                       f'name="{name}"\r\n\r\n{value}\r\n').encode())
    # Use a fixed safe filename in the multipart header.
    suffix = path.suffix.lower()
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; '
                   f'name="file"; filename="audio{suffix}"\r\n'
                   f'Content-Type: {mime}\r\n\r\n').encode())
    chunks.extend([path.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()])
    return boundary, b''.join(chunks)


def stamp(seconds, separator=','):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02}{separator}{ms:03}'


def export(result, prefix):
    # Retain the raw recognition response, including trace_id and speaker IDs.
    prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(str(prefix) + '.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    segments = result.get('segments')
    if not isinstance(segments, list) or not segments:
        raise ValueError('No timestamped segments returned; raw response saved')
    srt, vtt = [], ['WEBVTT\n']
    last_start = -1
    for i, item in enumerate(segments, 1):
        start, end = float(item['start']), float(item['end'])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
            raise ValueError('Invalid timestamp in ASR response')
        if start < last_start:
            raise ValueError('ASR segments are not ordered by start time')
        last_start = start
        text = item['text'].replace('\r', ' ').replace('\n', ' ')
        # Raw JSON preserves speaker IDs; do not guess their character names.
        srt.append(f'{i}\n{stamp(start)} --> {stamp(end)}\n{text}')
        vtt.append(f'{i}\n{stamp(start, ".")} --> {stamp(end, ".")}\n{text}')
    Path(str(prefix) + '.words.srt').write_text('\n\n'.join(srt) + '\n')
    Path(str(prefix) + '.words.vtt').write_text('\n\n'.join(vtt) + '\n')
    return len(segments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path)
    parser.add_argument('--output-prefix', type=Path)
    parser.add_argument('--language', default='zh')
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error('Audio file does not exist')
    if args.audio.stat().st_size > 50 * 1024 * 1024:
        parser.error('Audio exceeds 50 MB')
    if args.audio.suffix.lower() == '.wav':
        with wave.open(str(args.audio)) as wav:
            if wav.getnframes() / wav.getframerate() > 500:
                parser.error('Audio exceeds 500 seconds')
    key = os.environ.get('MINIMAX_API_KEY', '').strip()
    if not key:
        parser.error('Set MINIMAX_API_KEY; a GID is not an API key')
    boundary, body = multipart(args.audio)
    request = urllib.request.Request(
        'https://api.minimax.io/v1/speech_to_text', data=body,
        headers={'Authorization': 'Bearer ' + key,
                 'Content-Type': 'multipart/form-data; boundary=' + boundary,
                 'language': args.language})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
        prefix = args.output_prefix or args.audio.with_suffix('.minimax')
        count = export(result, prefix)
        print(json.dumps({'units': count, 'duration': result.get('duration'),
                          'n_speakers': result.get('n_speakers'),
                          'output_prefix': str(prefix.resolve())}, ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f'HTTP {exc.code}: ' + exc.read().decode(errors='replace')[:1500].replace(key, '[REDACTED]'))
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(str(exc).replace(key, '[REDACTED]'))


if __name__ == '__main__':
    main()
