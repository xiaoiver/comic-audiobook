"""Render the next comic scene using original page 8-9 panels."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
import render_comic_video as base

ROOT = base.ROOT
OUT = ROOT/'output/video/scene-02'
AUDIO = ROOT/'output/audio/ta2a/scene-02.wav'
META = json.loads(AUDIO.with_suffix('.json').read_text())
SENTENCES = META['subtitle']['sentences']
base.IMAGES.update({p.stem:Image.open(p).convert('RGB') for p in (OUT/'assets').glob('*.png')})
SHOTS = [
    (0, 3.1, 'table', '延续隔桌谈话'),
    (3.1, 5.8, 'bars', '隔着栏杆观察两人'),
    (5.8, 10.8, 'batman', '认真劝说'),
    (10.8, 13.5, 'batman_close', '语气转硬'),
    (13.5, 14.6, 'grab', '抓住手腕'),
    (14.6, 18.7, 'paint', '手套上的白色颜料'),
    (18.7, 20, 'stand', '起身靠近对方'),
    (20, 22.4, 'touch', '触碰脸上的化妆'),
    (22.4, 25.65, 'impostor', '替身惊慌抗议'),
    (25.65, 30, 'demand', '近距离逼问'),
]


def speaker(text):
    if text.startswith('他的手套'):
        return '旁白'
    if text.startswith(('嘿','等等','别碰我','我有权利','你不能这样')):
        return '囚犯'
    return '蝙蝠侠'


def compose(t):
    start,end,name,_ = next((s for s in SHOTS if s[0]<=t<s[1]), SHOTS[-1])
    p = (t-start)/(end-start)
    f = Image.new('RGB', (base.W,base.H), base.BG)
    panel = base.panel
    if name=='table':
        panel(f,'silent_man',(180,100,620,800),p,contain=True,brightness=.85)
        panel(f,'batman',(940,100,720,800),p,contain=True)
    elif name=='bars':
        panel(f,'bars',(260,120,1400,760),p,contain=True)
    elif name=='batman':
        panel(f,'batman',(160,100,700,800),p,contain=True)
        panel(f,'card_hands',(980,200,730,600),p,contain=True,brightness=.8)
    elif name=='batman_close':
        panel(f,'batman_face',(380,100,1160,800),p,zoom=.055,center=(.5,0))
    elif name=='grab':
        panel(f,'grab',(480,100,960,800),p,contain=True)
    elif name=='paint':
        panel(f,'paint',(435,100,1050,800),p,contain=True)
    elif name=='stand':
        panel(f,'stand',(490,100,940,800),p,contain=True)
    elif name=='touch':
        panel(f,'face_touch',(380,100,1160,800),p,contain=True)
    elif name=='impostor':
        panel(f,'impostor',(440,100,1040,800),p,contain=True)
    else:
        # The final question motivates a short push, then a sustained hold.
        cue=next(s['start_time']/1000 for s in SENTENCES if s['text'].startswith('他在哪'))
        q=base.ease((t-cue)/.32)
        w,h=round(1760*(.955+.045*q)),round(800*(.955+.045*q))
        panel(f,'demand',((1920-w)//2,100+(800-h)//2,w,h),1,contain=True)
    d=ImageDraw.Draw(f)
    d.text((80,44),'BATMAN  /  THE KILLING JOKE',font=base.LATIN,fill=(126,130,143))
    label='阿卡姆 · 破绽'
    d.text((base.W-80-d.textlength(label,font=base.SMALL),42),label,font=base.SMALL,fill=(126,130,143))
    current=next((s for s in SENTENCES if s['start_time']<=t*1000<s['end_time']+80),None)
    if current:
        text=current['text'];role=speaker(text)
        color=(192,173,156) if role=='囚犯' else base.ACCENT
        x=(base.W-d.textlength(text,font=base.FONT))/2
        d.text(((base.W-d.textlength(role,font=base.SMALL))/2,927),role,font=base.SMALL,fill=color)
        d.text((x,969),text,font=base.FONT,fill=(239,238,235))
        offset=0
        for word in current.get('words',[]):
            if word['start_time']<=t*1000<word['end_time']:
                d.text((x+d.textlength(text[:offset],font=base.FONT),969),word['text'],font=base.FONT,fill=color)
                break
            offset+=len(word['text'])
    fade=min(1,t/.2,(30-t)/.25)
    if fade<1:
        f=Image.blend(Image.new('RGB',f.size,base.BG),f,max(0,fade))
    return f


def main():
    global OUT, AUDIO, META, SENTENCES, SHOTS
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--audio',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    if args.audio:
        AUDIO=args.audio.resolve();META=json.loads(AUDIO.with_suffix('.json').read_text());SENTENCES=META['subtitle']['sentences']
        def cue(prefix,key='start_time'):
            return next(s[key]/1000 for s in SENTENCES if s['text'].startswith(prefix))
        plea=cue('我只想');question=cue('你到底');narrator=cue('他的手套')
        narrator_end=cue('他的手套','end_time');victim=cue('嘿');final_start=cue('他在哪')
        early=next((s['start_time']/1000 for s in SENTENCES if s['text'].startswith('或早')),plea*.55)
        points=[0,early,plea-.15,question-.15,narrator-.65,narrator,
                min(narrator_end+.15,victim-.2),victim,
                victim+(final_start-victim)*.48,final_start-.3,30]
        assert all(a<b for a,b in zip(points,points[1:])),points
        SHOTS=[(points[i],points[i+1],s[2],s[3]) for i,s in enumerate(SHOTS)]
    if args.output_dir:OUT=args.output_dir.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    shots=[dict(start=a,end=b,layout=c,description=d) for a,b,c,d in SHOTS]
    timeline={'duration_seconds':30,'global_start_seconds':30,'fps':24,'resolution':[1920,1080],
              'audio':str(AUDIO),'audio_request_id':META['request_id'],'shots':shots,
              'subtitles':[dict(s,speaker=speaker(s['text'])) for s in SENTENCES],
              'reference_files':META['reference_files'],'source_pdf':base.SOURCE_PDF,
              'note':'依据原漫画第8-9页节选改编；镜头和动作声时刻为编辑设定，字幕来自Seed返回时间戳。'}
    (OUT/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
    srt='\n\n'.join(f"{i}\n{base.timestamp(s['start_time'])} --> {base.timestamp(s['end_time'])}\n{s['text']}" for i,s in enumerate(SENTENCES,1))+'\n'
    (OUT/'scene-02.zh.srt').write_text(srt)
    if args.preview:
        sheet=Image.new('RGB',(1440,930),(20,20,25));d=ImageDraw.Draw(sheet)
        for i,t in enumerate([1.5,4.5,8,12,14,16.5,21,24,27.5]):
            im=compose(t);im.save(OUT/f'preview-{t:04.1f}.jpg',quality=92)
            x=i%3*480;y=i//3*310;sheet.paste(im.resize((480,270)),(x,y));d.text((x+8,y+278),f'{t:.1f}s',font=base.LATIN,fill='white')
        sheet.save(OUT/'storyboard.jpg',quality=93);print('Previews ready');return
    ff=base.imageio_ffmpeg.get_ffmpeg_exe()
    target=OUT/'batman-scene-02.mp4'
    cmd=[ff,'-y','-v','warning','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','24','-i','pipe:0',
         '-i',str(AUDIO),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18',
         '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','30','-movflags','+faststart',str(target)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for n in range(720):
            proc.stdin.write(compose(n/24).tobytes())
            if n%120==0: print(f'Rendered {n}/720',flush=True)
        proc.stdin.close()
        if proc.wait():raise RuntimeError('Render failed')
    except BaseException:
        proc.kill();proc.wait();raise
    print(target)


if __name__=='__main__':main()
