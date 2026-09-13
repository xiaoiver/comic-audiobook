#!/usr/bin/env python3
"""Export Seed timestamps; this validates metadata, not spoken pronunciation."""
import argparse
import copy
import json
import math
from pathlib import Path


def milliseconds(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Timestamps must be finite, nonnegative milliseconds')
    return round(value)


def timestamp(value):
    h, value = divmod(milliseconds(value), 3600000)
    m, value = divmod(value, 60000); s, ms = divmod(value, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def convert(metadata, offset_ms=0):
    offset_ms = milliseconds(offset_ms)
    sentences = copy.deepcopy(metadata.get('subtitle', {}).get('sentences', []))
    if not sentences:
        raise ValueError('No sentence timestamps; do not fabricate subtitles')
    previous = -1
    for s in sentences:
        a, b = milliseconds(s['start_time']), milliseconds(s['end_time'])
        if a < previous or b <= a or not isinstance(s.get('text'), str) or not s['text']:
            raise ValueError('Invalid sentence text, duration or ordering')
        previous = a
        word_start = a
        for w in s.get('words', []):
            x, y = milliseconds(w['start_time']), milliseconds(w['end_time'])
            if not a <= x <= y <= b or x < word_start:
                raise ValueError('Word timestamp outside sentence or out of order')
            word_start = x
            w['start_time'], w['end_time'] = x + offset_ms, y + offset_ms
        s['start_time'], s['end_time'] = a + offset_ms, b + offset_ms
    srt = '\n\n'.join(f"{i}\n{timestamp(s['start_time'])} --> {timestamp(s['end_time'])}\n{s['text']}"
                        for i, s in enumerate(sentences, 1)) + '\n'
    return sentences, srt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('metadata', type=Path)
    p.add_argument('--output-prefix', required=True, type=Path)
    p.add_argument('--offset-seconds', type=float, default=0)
    args = p.parse_args()
    sentences, srt = convert(json.loads(args.metadata.read_text(encoding='utf-8')), args.offset_seconds * 1000)
    paths = [Path(str(args.output_prefix) + suffix) for suffix in ('.srt', '.words.json')]
    if any(path.exists() for path in paths):
        raise FileExistsError('Subtitle version exists; use a new output prefix')
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(srt, encoding='utf-8')
    paths[1].write_text(json.dumps({'source': str(args.metadata.resolve()),
        'offset_ms': round(args.offset_seconds * 1000), 'sentences': sentences,
        'independent_asr': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n'.join(str(p.resolve()) for p in paths))


if __name__ == '__main__':
    main()
