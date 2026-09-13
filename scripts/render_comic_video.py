"""Render the 30-second comic pilot from original panels and Seed Audio timing."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = os.environ.get('COMIC_SOURCE_PDF')
sys.path.insert(0, str(ROOT / 'tmp/video_deps'))
import imageio_ffmpeg

W, H, FPS = 1920, 1080, 24
OUT = ROOT / 'output/video'
ASSETS = OUT / 'assets'
AUDIO = ROOT / 'output/audio/ta2a/batman-timed-sfx-sample.wav'
META = json.loads(AUDIO.with_suffix('.json').read_text())
SENTENCES = META['subtitle']['sentences']
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 46)
SMALL = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 22)
LATIN = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 22)
IMAGES = {p.stem: Image.open(p).convert('RGB') for p in ASSETS.glob('*.png')}
ACCENT = (213, 198, 151)
BG = (9, 10, 14)

# Rectangles: x, y, width, height. Each shot preserves a focal subject.
SHOTS = [
    dict(start=0, end=1.6, name='雨落积水', layout='rain', pages=[5], motion='水面缓慢推近', sound='雨声'),
    dict(start=1.6, end=3.55, name='阿卡姆门前', layout='arrival', pages=[5], motion='三格依次引导视线', sound='雨、浅水脚步、披风'),
    dict(start=3.55, end=5.85, name='走廊与钥匙', layout='corridor', pages=[6], motion='走廊到看守的顺序显现', sound='脚步、钥匙与开门声的预设区间'),
    dict(start=5.85, end=9.5, name='进入牌桌房间', layout='room', pages=[7], motion='完整房间关系、缓慢推近', sound='开门后室内空间、落座声'),
    dict(start=9.5, end=13.3, name='我来谈谈', layout='conversation', pages=[8], motion='蝙蝠侠近景为主、对面反应为辅', sound='蝙蝠侠对白'),
    dict(start=13.3, end=14.0, name='纸牌回应', layout='cards', pages=[8], motion='硬切手部特写', sound='抽牌、轻落牌'),
    dict(start=14.0, end=17.5, name='你和我', layout='conversation', pages=[8], motion='蝙蝠侠缓慢推近', sound='蝙蝠侠对白'),
    dict(start=17.5, end=20.05, name='沉默的对面', layout='reaction', pages=[8,7], motion='反应镜头停留', sound='蝙蝠侠画外对白'),
    dict(start=20.05, end=23.65, name='最后的问题', layout='eyes', pages=[8], motion='低幅度推近眼神', sound='我们会杀死对方，对吗'),
    dict(start=23.65, end=26.6, name='没有回答', layout='reaction', pages=[8,7], motion='保持沉默的反应画面', sound='女旁白收尾'),
    dict(start=26.6, end=30, name='纸牌落桌', layout='cards', pages=[8], motion='手部特写、结尾轻收暗', sound='女旁白、落牌声'),
]


def ease(t):
    t = max(0, min(1, t))
    return (1 - math.cos(math.pi * t)) / 2


def panel(canvas, name, rect, progress, zoom=0.035, center=(0.5,0.5), contain=False, brightness=1):
    x,y,w,h = map(int, rect)
    src = IMAGES[name]
    q = ease(progress)
    if contain:
        scale = min(w/src.width, h/src.height)
        sw,sh = round(src.width*scale),round(src.height*scale)
        tile = src.resize((sw,sh), Image.Resampling.LANCZOS)
        # Scale motion stays within the reserved cell, never cutting a head.
        tile = tile.resize((round(sw*(.975+.025*q)),round(sh*(.975+.025*q))),Image.Resampling.BICUBIC)
        if brightness != 1:
            tile = tile.point(lambda v: int(v*brightness))
        canvas.paste(tile,(x+(w-tile.width)//2,y+(h-tile.height)//2))
        return
    scale = max(w/src.width,h/src.height)*(1+zoom*q)
    cw,ch = w/scale,h/scale
    cx = max(cw/2,min(src.width-cw/2,src.width*center[0]))
    cy = max(ch/2,min(src.height-ch/2,src.height*center[1]))
    # A tiny diagonal drift accompanies the zoom, clamped to the image.
    cx = max(cw/2,min(src.width-cw/2,cx+src.width*.012*(q-.5)))
    tile = src.transform((w,h),Image.Transform.EXTENT,(cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2),Image.Resampling.BICUBIC)
    if brightness != 1:
        tile = tile.point(lambda v:int(v*brightness))
    canvas.paste(tile,(x,y))


def compose(t):
    shot = next((s for s in SHOTS if s['start']<=t<s['end']),SHOTS[-1])
    p=(t-shot['start'])/(shot['end']-shot['start'])
    frame=Image.new('RGB',(W,H),BG)
    layout=shot['layout']
    if layout=='rain':
        panel(frame,'rain',(80,100,1760,800),p,zoom=.055)
    elif layout=='arrival':
        for i,name in enumerate(['gate','boot','arrival']):
            panel(frame,name,(80+i*592,100,576,800),p,contain=True,brightness=1 if i==2 else .91)
    elif layout=='corridor':
        for i,name in enumerate(['entrance','corridor','keys']):
            reveal=ease((p-i*.17)/.25)
            panel(frame,name,(80+i*592,100,576,800),p,contain=True,brightness=.15+.85*reveal)
    elif layout=='room':
        panel(frame,'doorway',(80,100,435,800),p,contain=True,brightness=.75)
        panel(frame,'room',(545,100,850,800),p,contain=True)
        panel(frame,'cards',(1425,100,415,800),p,contain=True,brightness=.85)
    elif layout=='conversation':
        panel(frame,'silent_man',(100,100,560,800),p,contain=True,brightness=.74)
        panel(frame,'batman_face',(720,100,1120,800),p,zoom=.045,center=(.5,0))
    elif layout=='reaction':
        panel(frame,'silent_man',(220,100,720,800),p,contain=True)
        panel(frame,'cards',(1040,130,610,740),p,contain=True,brightness=.79)
    elif layout=='eyes':
        panel(frame,'batman_eyes',(140,100,1640,800),p,zoom=.075,center=(.5,.35))
    elif layout=='cards':
        panel(frame,'card_hands',(390,100,1140,800),p,zoom=.035,center=(.53,.42))
    draw=ImageDraw.Draw(frame)
    draw.text((80,44),'BATMAN  /  THE KILLING JOKE',font=LATIN,fill=(126,130,143))
    label='阿卡姆 · 雨夜'
    draw.text((W-80-draw.textlength(label,font=SMALL),42),label,font=SMALL,fill=(126,130,143))
    # A very subtle weather layer only on the exterior establishing shots.
    if t<3.55:
        layer=Image.new('RGBA',(W,H),(0,0,0,0));ld=ImageDraw.Draw(layer)
        for i in range(55):
            rx=80+(i*137+int(t*38))%1760
            ry=100+int(i*89+t*(290+i%7*20))%760
            ld.line((rx,ry,rx-5,ry+20),fill=(185,201,228,27),width=1)
        frame=Image.alpha_composite(frame.convert('RGBA'),layer).convert('RGB')
        draw=ImageDraw.Draw(frame)
    current=next((s for s in SENTENCES if s['start_time']<=t*1000<s['end_time']+120),None)
    if current:
        text=current['text']
        speaker='蝙蝠侠' if 9.5<=current['start_time']/1000<24 else '旁白'
        tw=draw.textlength(text,font=FONT)
        left=(W-tw)/2
        draw.text(((W-draw.textlength(speaker,font=SMALL))/2,927),speaker,font=SMALL,fill=ACCENT if speaker=='蝙蝠侠' else (134,141,156))
        draw.text((left,969),text,font=FONT,fill=(239,238,235))
        # Highlight only the currently timed character, leaving punctuation intact.
        offset=0
        for word in current.get('words',[]):
            if word['start_time']<=t*1000<word['end_time']:
                prefix=text[:offset]
                draw.text((left+draw.textlength(prefix,font=FONT),969),word['text'],font=FONT,fill=ACCENT)
                break
            offset+=len(word['text'])
    # Short opening/closing fades; subtle camera motion continues beneath them.
    fade=min(1,t/.3) if t<.3 else (max(0,(30-t)/.25) if t>29.75 else 1)
    if fade<1:
        frame=Image.blend(Image.new('RGB',(W,H),BG),frame,fade)
    return frame


def timestamp(ms,sep=','):
    h,ms=divmod(int(ms),3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02}{sep}{ms:03}'


def deliver_metadata():
    timeline={'resolution':[W,H],'fps':FPS,'duration_seconds':30,'source_pdf':SOURCE_PDF,'audio':str(AUDIO),'audio_request_id':META['request_id'],'shots':SHOTS,'subtitles':SENTENCES,'notes':['镜头切点依据实际台词时间校准；音效位置为提示词目标，未通过独立识别器确定。','角色标签依据脚本绑定，不是ASR识别。','保留原漫画线条和画格，未生成或重画人物。']}
    (OUT/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
    srt='\n\n'.join(f"{i}\n{timestamp(s['start_time'])} --> {timestamp(s['end_time'])}\n{s['text']}" for i,s in enumerate(SENTENCES,1))+'\n'
    (OUT/'batman-pilot.zh.srt').write_text(srt)


def main():
    global AUDIO, META, SENTENCES, OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--audio',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    if args.audio:
        AUDIO=args.audio.resolve()
        META=json.loads(AUDIO.with_suffix('.json').read_text())
        SENTENCES=META['subtitle']['sentences']
    if args.output_dir:
        OUT=args.output_dir.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    deliver_metadata()
    if args.preview:
        times=[.8,2.3,4.8,7.8,11.6,13.65,15.6,18.5,21.5,24.7,28.2,29.5]
        sheet=Image.new('RGB',(1440,4*310),(24,24,28));d=ImageDraw.Draw(sheet)
        for i,t in enumerate(times):
            im=compose(t);im.save(OUT/f'preview-{t:04.1f}.jpg',quality=92)
            thumb=im.resize((480,270),Image.Resampling.LANCZOS)
            x=(i%3)*480;y=(i//3)*310;sheet.paste(thumb,(x,y));d.text((x+8,y+278),f'{t:.1f}s',font=LATIN,fill='white')
        sheet.save(OUT/'storyboard-contact.jpg',quality=93)
        print('Previews ready',flush=True);return
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    target=OUT/'batman-killing-joke-pilot.mp4'
    command=[ffmpeg,'-y','-hide_banner','-loglevel','warning','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(AUDIO),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','afade=t=out:st=29.8:d=0.2','-t','30','-movflags','+faststart',str(target)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for n in range(30*FPS):
            proc.stdin.write(compose(n/FPS).tobytes())
            if n%120==0:print(f'Rendered {n}/{30*FPS} frames',flush=True)
        proc.stdin.close()
        status=proc.wait()
        if status:raise RuntimeError(f'ffmpeg exited {status}')
    except BaseException:
        proc.kill();proc.wait();raise
    print(str(target),flush=True)


if __name__=='__main__':
    main()
