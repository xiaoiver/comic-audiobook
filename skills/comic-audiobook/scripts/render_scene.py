#!/usr/bin/env python3
"""Render a configurable original-panel scene; no story or machine paths baked in."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont


def ffmpeg_path():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError('Install/provide FFmpeg or imageio-ffmpeg') from None


def rectangle(value):
    if len(value) != 4 or any(not math.isfinite(x) for x in value):
        raise ValueError('Rectangle must contain four finite numbers')
    x, y, w, h = value
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1
            and x + w <= 1.000001 and y + h <= 1.000001):
        raise ValueError('Rectangle outside normalized canvas')
    return value


class Scene:
    def __init__(self, path):
        path = Path(path).resolve(); self.root = path.parent
        c = json.loads(path.read_text(encoding='utf-8')); self.config = c
        self.width, self.height = c.get('size', [1920, 1080]); self.fps = c.get('fps', 24)
        if any(not isinstance(x, int) or x <= 0 for x in (self.width, self.height, self.fps)):
            raise ValueError('Size and FPS must be positive integers')
        if self.width % 2 or self.height % 2:
            raise ValueError('H.264 yuv420p requires even dimensions')
        self.audio = (self.root / c['audio']).resolve()
        with wave.open(str(self.audio)) as w:
            self.duration = w.getnframes() / w.getframerate()
        if self.duration <= 0:
            raise ValueError('Audio is empty')
        self.frames = math.ceil(self.duration * self.fps)
        self.images = {name: Image.open(self.root / value).convert('RGB') for name, value in c['images'].items()}
        self.shots = c['shots']; previous = 0
        for shot in self.shots:
            start, end = shot['start'], shot['end']
            if not all(math.isfinite(x) for x in (start, end)) or abs(start-previous) > .001 or end <= start:
                raise ValueError('Shots must be ordered, contiguous and positive duration')
            previous = end
            if not shot.get('panels'):
                raise ValueError('Each shot needs panels')
            for panel in shot['panels']:
                if panel['image'] not in self.images:
                    raise ValueError('Unknown image name')
                rectangle(panel['rect'])
                mode = panel.get('fit', 'contain')
                if mode not in ('contain', 'cover'):
                    raise ValueError('fit must be contain or cover')
                zoom = panel.get('zoom', [.98, 1] if mode == 'contain' else [1, 1.04])
                if len(zoom) != 2 or any(not math.isfinite(z) or z <= 0 for z in zoom):
                    raise ValueError('Zoom needs two positive factors')
                if mode == 'contain' and max(zoom) > 1:
                    raise ValueError('contain zoom must not exceed 1; use cover for intentional cropping')
                if mode == 'cover' and min(zoom) < 1:
                    raise ValueError('cover zoom must not be below 1')
                panel['_zoom'] = zoom
                if any(not 0 <= v <= 1 for v in panel.get('focus', [.5, .5])) or len(panel.get('focus', [.5, .5])) != 2:
                    raise ValueError('Focus must be two normalized coordinates')
        if not self.shots or abs(previous-self.duration) > .001:
            raise ValueError('Last shot must end at actual WAV duration')
        self.sentences = c.get('subtitles', [])
        self.font_path = self.root / c['font'] if self.sentences else None
        self.caption_rect = rectangle(c.get('caption_rect', [.04, .83, .92, .15]))
        for sentence in self.sentences:
            if not (0 <= sentence['start_time'] < sentence['end_time'] <= self.duration*1000 + 1):
                raise ValueError('Subtitle outside actual audio duration')
        self.background = tuple(c.get('background', [9, 10, 14]))

    def caption(self, frame, sentence, t):
        x, y, w, h = [round(v*d) for v,d in zip(self.caption_rect,[self.width,self.height,self.width,self.height])]
        d = ImageDraw.Draw(frame); text = sentence['text']
        d.rectangle((x,y,x+w,y+h), fill=self.background)
        # Fit text at character boundaries, never silently truncate a long line.
        initial = max(14, round(self.height*.043))
        for size in range(initial, max(9, initial//2)-1, -1):
            font = ImageFont.truetype(str(self.font_path), size)
            lines = []; line = ''; offset = 0
            for char in text:
                if line and d.textlength(line+char,font=font) > w:
                    lines.append((offset,line)); offset += len(line); line = ''
                line += char
            if line: lines.append((offset,line))
            if len(lines) <= 2: break
        if len(lines) > 2:
            raise ValueError('Caption too long; split at word timestamps rather than truncate')
        label = sentence.get('speaker', '')
        small = ImageFont.truetype(str(self.font_path), max(10,round(size*.52)))
        d.text((x+(w-d.textlength(label,font=small))/2,y),label,font=small,fill=(180,174,153))
        active = set(); words = sentence.get('words', [])
        if ''.join(word['text'] for word in words) == text:
            offset = 0
            for word in words:
                if word['start_time'] <= t*1000 < word['end_time']:
                    active.update(range(offset,offset+len(word['text'])))
                offset += len(word['text'])
        for row,(offset,line) in enumerate(lines):
            lx = x+(w-d.textlength(line,font=font))/2; ly = y+round(size*.75)+row*round(size*1.2)
            if ly+size > y+h:
                raise ValueError('Caption area too short')
            d.text((lx,ly),line,font=font,fill=(239,238,235))
            for i,char in enumerate(line):
                if offset+i in active:
                    d.text((lx+d.textlength(line[:i],font=font),ly),char,font=font,fill=(213,198,151))

    def frame(self, t):
        shot = next((s for s in self.shots if s['start'] <= t < s['end']), self.shots[-1])
        p = min(1,max(0,(t-shot['start'])/(shot['end']-shot['start'])))
        eased = (1-math.cos(math.pi*p))/2
        frame = Image.new('RGB',(self.width,self.height),self.background)
        for panel in shot['panels']:
            source = self.images[panel['image']]
            x,y,w,h = [round(v*d) for v,d in zip(panel['rect'],[self.width,self.height,self.width,self.height])]
            a,b = panel['_zoom']; zoom = a+(b-a)*eased
            if panel.get('fit','contain') == 'contain':
                scale = min(w/source.width,h/source.height)*zoom
                tile = source.resize((max(1,round(source.width*scale)),max(1,round(source.height*scale))),Image.Resampling.LANCZOS)
                frame.paste(tile,(x+(w-tile.width)//2,y+(h-tile.height)//2))
            else:
                scale = max(w/source.width,h/source.height)*zoom
                cw,ch = w/scale,h/scale; fx,fy = panel.get('focus',[.5,.5])
                cx = max(cw/2,min(source.width-cw/2,fx*source.width))
                cy = max(ch/2,min(source.height-ch/2,fy*source.height))
                tile = source.transform((w,h),Image.Transform.EXTENT,
                    (cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2),Image.Resampling.BICUBIC)
                frame.paste(tile,(x,y))
        current = next((s for s in self.sentences if s['start_time'] <= t*1000 < s['end_time']),None)
        if current: self.caption(frame,current,t)
        return frame


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('timeline',type=Path); p.add_argument('--output',required=True,type=Path)
    p.add_argument('--preview-at',type=float)
    args = p.parse_args(); scene = Scene(args.timeline)
    if args.output.exists(): raise FileExistsError('Use a new output version')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.preview_at is not None:
        if not 0 <= args.preview_at < scene.duration: raise ValueError('Preview outside scene')
        scene.frame(args.preview_at).save(args.output); return
    if args.output.suffix.lower() != '.mp4': raise ValueError('Video output must be MP4')
    stage = args.output.with_name(args.output.stem+'.partial.mp4')
    if stage.exists(): raise FileExistsError('Partial render already exists; inspect it first')
    command = [ffmpeg_path(),'-n','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',
        f'{scene.width}x{scene.height}','-r',str(scene.fps),'-i','pipe:0','-i',str(scene.audio),
        '-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18',
        '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','apad','-t',str(scene.frames/scene.fps),
        '-movflags','+faststart',str(stage)]
    proc = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for n in range(scene.frames): proc.stdin.write(scene.frame(n/scene.fps).tobytes())
        proc.stdin.close(); error = proc.stderr.read().decode(errors='replace')
        if proc.wait(): raise RuntimeError(error)
        stage.replace(args.output)
    except BaseException:
        proc.kill(); proc.wait(); raise
    print(args.output.resolve())


if __name__ == '__main__': main()
