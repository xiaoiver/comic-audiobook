"""Mix scene two and assemble an optional 60-second continuation preview."""
import json
import re
import subprocess
from pathlib import Path
import wave
import hashlib
import argparse

import numpy as np
import mix_cinematic_v2 as util

ROOT=util.ROOT
OUT=ROOT/'output/video/scene-02'
AUDIO=ROOT/'output/audio/ta2a/scene-02.wav'
SR=util.SR
N=30*SR


def main():
    global OUT, AUDIO
    parser=argparse.ArgumentParser()
    parser.add_argument('--audio',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--prompt',type=Path,default=AUDIO.parent/'scene-02-prompt.txt')
    parser.add_argument('--combined',type=Path,default=ROOT/'output/video/batman-60s.mp4')
    args=parser.parse_args()
    if args.audio:AUDIO=args.audio.resolve()
    if args.output_dir:OUT=args.output_dir.resolve()
    meta=json.loads(AUDIO.with_suffix('.json').read_text())
    sentences=meta['subtitle']['sentences']
    # Current prompts reserve Chinese quotation marks exclusively for dialogue.
    expected=''.join(re.findall(r'“([^”]*)”',args.prompt.read_text()))
    assert ''.join(s['text'] for s in sentences)==expected
    original=util.read(AUDIO);assert len(original)==N
    t=np.arange(N)/SR;spoken=np.zeros(N)
    for s in sentences:
        assert 0<=s['start_time']<s['end_time']<=30000
        a,b=s['start_time']/1000,s['end_time']/1000
        spoken=np.maximum(spoken,np.minimum(np.clip((t-a+.1)/.1,0,1),np.clip((b+.16-t)/.16,0,1)))
    voiced_rms=np.sqrt(np.mean(original[spoken>.9]**2))
    gain=min(10**(-22/20)/voiced_rms,.6/np.max(abs(original)))
    mix=original*gain
    music=util.read(util.ASSETS/'suspense-bgm.wav')[:N]
    music*=10**(-27/20)/np.sqrt(np.mean(music**2))
    music*=10**(-5*spoken[:,None]/20)
    final_line=next(s for s in sentences if s['text'].startswith('他在哪'))
    final_start=final_line['start_time']/1000
    final_end=final_line['end_time']/1000
    def cue(prefix,key='start_time'):
        return next(s[key]/1000 for s in sentences if s['text'].startswith(prefix))
    narrator=cue('他的手套');narrator_end=cue('他的手套','end_time');victim=cue('嘿')
    music_times=[0,.5,cue('你到底'),narrator-.3,narrator,narrator_end,victim,
                 final_start-.8,final_start-.3]
    music_levels=[0,.7,1,1.1,.09,.1,.7,1.2,.025]
    if final_end+.85<30:
        music_times += [final_end+.4,final_end+.65]
        music_levels += [.025,.7]
    music_times += [30];music_levels += [0]
    assert all(a<b for a,b in zip(music_times,music_times[1:]))
    music*=np.interp(t,music_times,music_levels)[:,None]
    mix+=music
    rain=util.peak_normalize(util.read(util.ASSETS/'rain-metal.wav'),-41)
    bed=np.zeros_like(mix)
    for start in np.arange(0,30,7.6):
        clip=util.fade(rain,.4);pos=round(start*SR);n=min(len(clip),N-pos)
        bed[pos:pos+n]+=clip[:n]
    mix+=bed
    placements=[]
    def place(path,start,peak,duration=None,event=None):
        clip=util.read(path)
        if duration:clip=clip[:round(duration*SR)]
        if event is not None:
            e=np.mean(clip**2,axis=1);b=240
            start=event-int(np.argmax([e[i:i+b].mean() for i in range(0,len(e),b)]))*b/SR
        clip=util.fade(util.peak_normalize(clip,peak),.05)
        pos=round(start*SR);n=min(len(clip),N-pos)
        mix[pos:pos+n]+=clip[:n]*10**(-2*spoken[pos:pos+n,None]/20)
        placements.append({'asset':str(path),'start_seconds':start,'duration_seconds':n/SR,'peak_before_duck_dbfs':peak})
    place(util.ASSETS/'card-table.wav',0,-19,event=cue('我只想')-.3)
    place(util.ASSETS/'card-table.wav',0,-21,event=cue('你到底')-.3)
    place(AUDIO.parent/'scene-02-foley.wav',narrator-.65,-15,duration=5)
    place(AUDIO.parent/'scene-02-foley.wav',final_start-1.4,-17,duration=1.05)
    mix*=np.minimum(1,(30-t)/.25)[:,None]
    if np.max(abs(mix))>.89:mix*=.89/np.max(abs(mix))
    premix=OUT/'scene-02-premix.wav';util.write(premix,mix)
    ff=util.imageio_ffmpeg.get_ffmpeg_exe();final_audio=OUT/'scene-02-mix.wav'
    subprocess.run([ff,'-y','-v','error','-i',str(premix),'-af','loudnorm=I=-17:TP=-1.5:LRA=11',
                    '-ar',str(SR),'-c:a','pcm_s16le',str(final_audio)],check=True)
    video=OUT/'batman-scene-02.mp4';staged=OUT/'mixed.mp4'
    subprocess.run([ff,'-y','-v','error','-i',str(video),'-i',str(final_audio),'-map','0:v:0','-map','1:a:0',
                    '-c:v','copy','-c:a','aac','-b:a','192k','-t','30','-movflags','+faststart',str(staged)],check=True)
    staged.replace(video)
    plan={'joint_generated_audio':str(AUDIO),'final_audio':str(final_audio),'dialogue_gain_db':float(20*np.log10(gain)),
          'bgm':str(util.ASSETS/'suspense-bgm.wav'),'music_duck_db':5,'foley':placements,
          'note':'音效类别以生成提示词为依据；混音与字幕已检查，未独立试听验收。'}
    (OUT/'mix-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    timeline=json.loads((OUT/'timeline.json').read_text());timeline['audio']=str(final_audio);timeline['sound_design']=plan
    (OUT/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
    voices_path=AUDIO.parent/'voices.json';voices=json.loads(voices_path.read_text())
    reference=AUDIO.parent/'impostor-reference.wav'
    with wave.open(str(reference)) as w:duration=w.getnframes()/w.getframerate()
    entry={'role':'冒充小丑的囚犯','reference':str(reference),'marker':'@音频3',
           'duration':duration,'sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
           'casting':'成年男声、偏高、略带鼻音、紧张；音色设定未独立试听验收'}
    voices=[v for v in voices if v['role']!=entry['role']]+[entry]
    voices_path.write_text(json.dumps(voices,ensure_ascii=False,indent=2))
    (OUT/'audio-qa.json').write_text(json.dumps({'subtitle_exact_match':True,'duration_seconds':30,
        'reference_files':meta['reference_files'],'no_pcm_clipping':bool(np.max(abs(util.read(final_audio)))<1)},ensure_ascii=False,indent=2))
    # Assemble both completed scenes, preserving 30 seconds for each.
    first=ROOT/'output/video/cinematic-v2/batman-killing-joke-pilot.mp4'
    combined=args.combined.resolve()
    listing=OUT/'concat.txt';listing.write_text(f"file '{first}'\nfile '{video}'\n")
    subprocess.run([ff,'-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c:v','copy',
                   '-c:a','aac','-b:a','192k','-t','60','-movflags','+faststart',str(combined)],check=True)
    import render_comic_video as base
    first_s=json.loads((first.parent/'timeline.json').read_text())['subtitles']
    all_s=first_s+[dict(s,start_time=s['start_time']+30000,end_time=s['end_time']+30000) for s in sentences]
    srt='\n\n'.join(f"{i}\n{base.timestamp(s['start_time'])} --> {base.timestamp(s['end_time'])}\n{s['text']}" for i,s in enumerate(all_s,1))+'\n'
    combined.with_suffix('.zh.srt').write_text(srt)
    print(video);print(combined)


if __name__=='__main__':main()
