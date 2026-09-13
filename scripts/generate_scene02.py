"""Create the new role first, then submit the scene with all three references."""
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/audio/ta2a'
key = os.environ.get('SEED_AUDIO_API_KEY') or sys.stdin.readline().strip()
if not key:
    raise SystemExit('Missing API key')

def generate(prompt, target, refs=()):
    cmd = [sys.executable, str(ROOT/'scripts/seed_audio_generate.py'), '--prompt', str(prompt),
           '--output', str(target), '--format', 'wav']
    for ref in refs:
        cmd.extend(['--reference', str(ref)])
    subprocess.run(cmd, input=key+'\n', text=True, check=True)

reference = OUT/'impostor-reference.wav'
if not reference.exists():
    generate(OUT/'impostor-reference.txt', reference)
generate(OUT/'scene-02-prompt.txt', OUT/'scene-02.wav',
         [OUT/'narrator-reference.wav', OUT/'batman-reference.wav', reference])
