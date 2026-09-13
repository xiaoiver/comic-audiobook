"""Enhance the joint Seed generation with generated ambience, foley and score."""
import json
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/video_deps'))
import imageio_ffmpeg

OUT = ROOT / 'output/video/cinematic-v2'
ASSETS = ROOT / 'output/audio/sound-design-v2'
VOICE = ROOT / 'output/audio/ta2a/batman-cinematic-v2.wav'
SR = 24000
N = 30 * SR


def read(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float)
        a = a.reshape(-1, w.getnchannels()) / 32768
    return np.repeat(a, 2, axis=1) if a.shape[1] == 1 else a


def write(path, a):
    assert np.max(np.abs(a)) < 1
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype('<i2').tobytes())


def peak_normalize(a, db):
    return a * (10 ** (db / 20)) / max(np.max(np.abs(a)), 1e-9)


def fade(a, seconds=.08):
    a = a.copy()
    n = min(int(seconds * SR), len(a) // 2)
    a[:n] *= np.linspace(0, 1, n)[:, None]
    a[-n:] *= np.linspace(1, 0, n)[:, None]
    return a


def main():
    meta = json.loads(VOICE.with_suffix('.json').read_text())
    t = np.arange(N) / SR
    spoken = np.zeros(N)
    for s in meta['subtitle']['sentences']:
        a, b = s['start_time'] / 1000, s['end_time'] / 1000
        duck = np.minimum(np.clip((t-a+.12)/.12, 0, 1), np.clip((b+.2-t)/.2, 0, 1))
        spoken = np.maximum(spoken, duck)
    # Smooth music ducking based on actual generated speech timings.
    music = read(ASSETS / 'suspense-bgm.wav')[:N]
    rms = np.sqrt(np.mean(music ** 2))
    music *= 10 ** (-25 / 20) / max(rms, 1e-9)
    music *= (10 ** (-6 * spoken / 20))[:, None]
    music *= np.interp(t, [0, .7, 20, 23.52, 23.9, 25.8, 26.6, 29.3, 30],
                      [0, .75, 1, 1, .05, .05, .6, .35, 0])[:, None]
    rain = read(ASSETS / 'rain-metal.wav')
    # Crossfade the rain loop for uninterrupted distant exterior ambience.
    rain = peak_normalize(rain, -17)
    rainbed = np.zeros((N, 2))
    for start in np.arange(0, 30, 7.6):
        clip = fade(rain, .4); pos = round(start * SR)
        count = min(len(clip), N-pos)
        rainbed[pos:pos+count] += clip[:count]
    rainbed *= np.interp(t, [0, .15, 3.25, 3.9, 29.5, 30], [0, 1, 1, .06, .06, 0])[:, None]
    rainbed *= (10 ** (-2 * spoken / 20))[:, None]
    effects = np.zeros((N, 2))
    placements = []

    def place(name, start, peak, duration=None, event_at=None):
        clip = read(ASSETS / (name + '.wav'))
        if duration is not None:
            clip = clip[:round(duration * SR)]
        if event_at is not None:
            # Align the strongest short energy burst to the intended card beat.
            energy = np.mean(clip ** 2, axis=1)
            block = 240
            buckets = [energy[i:i+block].mean() for i in range(0, len(energy), block)]
            offset = int(np.argmax(buckets)) * block / SR
            start = event_at - offset
        clip = fade(peak_normalize(clip, peak))
        pos = round(start * SR)
        if pos < 0:
            clip = clip[-pos:]; pos = 0
        count = min(len(clip), N-pos)
        effects[pos:pos+count] += clip[:count]
        placements.append({'asset': name, 'start_seconds': pos/SR,
                           'end_seconds': (pos+count)/SR, 'peak_target_dbfs': peak,
                           'strongest_burst_target_seconds': event_at})

    place('boots-corridor', 3.45, -14, duration=4.8)
    place('lock-door', 4.75, -18, duration=4.1)
    place('card-table', 0, -17, event_at=13.65)
    place('card-table', 0, -13, event_at=29.1)
    original = read(VOICE)
    mix = original * 10 ** (4/20) + music + rainbed + effects
    mix *= np.minimum(1, (30-t)/.2)[:, None]
    peak = float(np.max(np.abs(mix)))
    if peak > .89:
        mix *= .89 / peak
    premix = OUT / 'cinematic-premix.wav'
    write(premix, mix)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    final_audio = OUT / 'batman-cinematic-v2-mix.wav'
    subprocess.run([ff, '-y', '-v', 'error', '-i', str(premix), '-af',
                    'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', str(SR),
                    '-c:a', 'pcm_s16le', str(final_audio)], check=True)
    video = OUT / 'batman-killing-joke-pilot.mp4'
    staged = OUT / 'enhanced.mp4'
    subprocess.run([ff, '-y', '-v', 'error', '-i', str(video), '-i', str(final_audio),
                    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
                    '-b:a', '192k', '-t', '30', '-movflags', '+faststart', str(staged)], check=True)
    staged.replace(video)
    plan = {'joint_generated_audio': str(VOICE), 'final_audio': str(final_audio),
            'bgm': str(ASSETS / 'suspense-bgm.wav'), 'music_rms_target_before_master_dbfs': -25,
            'dialogue_music_duck_db': 6, 'foley': placements,
            'loudness_target_lufs': -16, 'true_peak_limit_dbfs': -1.5,
            'note': '提示词联合生成后补充独立Seed音效与配乐，未修改对白时间。动作声类别来自生成提示词，未独立试听验证。'}
    (OUT / 'mix-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    timeline = json.loads((OUT / 'timeline.json').read_text())
    timeline['audio'] = str(final_audio)
    timeline['sound_design'] = plan
    (OUT / 'timeline.json').write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    print(video)


if __name__ == '__main__':
    main()
