"""Independent local ASR; never provide the expected transcript as a prompt."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/asr_deps'))
os.environ['HF_HOME']=str(ROOT/'tmp/asr_cache')
os.environ['HF_HUB_DISABLE_XET']='1'
from faster_whisper import WhisperModel

parser=argparse.ArgumentParser()
parser.add_argument('audio',type=Path)
parser.add_argument('--model',default='base')
args=parser.parse_args()
model=WhisperModel(args.model,device='cpu',compute_type='int8',cpu_threads=4,
                   download_root=str(ROOT/'tmp/asr_models'))
segments,info=model.transcribe(str(args.audio),language='zh',beam_size=5,
                              condition_on_previous_text=False,word_timestamps=True)
rows=[]
for s in segments:
    row={'start':s.start,'end':s.end,'text':s.text,
         'words':[{'word':w.word,'start':w.start,'end':w.end,'probability':w.probability} for w in s.words or []]}
    rows.append(row)
    print(f'{s.start:.2f}-{s.end:.2f}: {s.text}',flush=True)
result={'model':'faster-whisper/'+args.model,'language':info.language,'segments':rows,
        'expected_transcript_supplied':False,'note':'Independent ASR can still misrecognize words; not a substitute for listening.'}
args.audio.with_suffix('.asr.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
