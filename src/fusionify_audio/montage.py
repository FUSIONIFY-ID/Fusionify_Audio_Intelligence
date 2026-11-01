"""Render validated scenes with original music using fixed FFmpeg filters."""
from __future__ import annotations

import math
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from .engine import DEMUXERS
from .render import dimensions


def run_process(args: list[str], cancel, timeout: float=120):
    started=time.monotonic()
    # A temporary file avoids stderr pipe deadlocks and keeps diagnostics local.
    with tempfile.TemporaryFile() as log:
        process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=log)
        try:
            while process.poll() is None:
                if cancel.is_set():raise RuntimeError('Render cancelled.')
                if time.monotonic()-started>timeout:raise RuntimeError('Render stage timed out.')
                time.sleep(.05)
            if process.returncode:
                log.seek(0)
                detail=log.read(2048).decode(errors='replace')
                raise RuntimeError('FFmpeg render stage failed: '+detail)
        finally:
            if process.poll() is None:process.kill()
            process.wait()


def filters(effect: str, width: int, height: int, frames: int, amount: float=.6, fit_mode: str='cover') -> str:
    base=f'fps=30,scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1'
    if fit_mode=='contain':base=f'fps=30,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x0d1627,setsar=1'
    if effect=='cut' or amount==0:return base
    if effect=='zoom':
        return base+f",scale={width*2}:{height*2},zoompan=z='1+{.08*amount:.5f}*on/{max(frames,1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=30"
    if effect=='pan':
        return base+f",scale={width+40}:{height+40},crop={width}:{height}:x='20+{16*amount:.5f}*sin(n/{max(frames,1)}*PI)':y=20"
    if effect=='shake':
        return base+f",scale={width+32}:{height+32},crop={width}:{height}:x='16+{10*amount:.5f}*sin(n*1.7)*exp(-n/8)':y='16+{6*amount:.5f}*cos(n*2.1)*exp(-n/8)'"
    raise ValueError('Unknown scene effect.')


def overlay_image(path: Path, width: int, height: int, title: str, caption: str):
    image=Image.new('RGBA',(width,height),(0,0,0,0));draw=ImageDraw.Draw(image)
    scale=min(width,height)/480
    try:
        bold=ImageFont.truetype('DejaVuSans-Bold.ttf',round(27*scale))
        small=ImageFont.truetype('DejaVuSans.ttf',round(16*scale))
    except OSError:
        bold=ImageFont.load_default(size=round(27*scale));small=ImageFont.load_default(size=round(16*scale))
    margin=round(28*scale)
    lines=[]
    for text,font in [(title,bold),(caption,small)]:
        line=''
        for word in text.split():
            trial=(line+' '+word).strip()
            if draw.textbbox((0,0),trial,font=font)[2]>width-2*margin and line:
                lines.append((line,font));line=word
            else:line=trial
        if line:lines.append((line,font))
    lines=lines[:4]
    line_height=round(35*scale)
    top=height-margin-line_height*len(lines)-margin
    draw.rectangle((0,top,width,height),fill=(0,0,0,165))
    for i,(text,font) in enumerate(lines):
        while text and draw.textbbox((0,0),text,font=font)[2]>width-2*margin:text=text[:-1]
        draw.text((margin,top+margin+i*line_height),text,font=font,fill=(255,255,255,255))
    image.save(path)


def montage(source: Path, timeline: dict, options: dict, media: dict,
            output: Path, cancel, progress):
    width,height=dimensions(options['aspect'],options['resolution'])
    duration=timeline['duration_s'];fps=30
    total_frames=max(1,math.ceil(duration*fps))
    if len(timeline['scenes'])>720:raise ValueError('Timeline exceeds the scene limit.')
    with tempfile.TemporaryDirectory(prefix='fai-shots-',dir=output.parent) as temp:
        folder=Path(temp);shots=[];image_cache={};video_offsets={};started=time.monotonic()
        for scene in timeline['scenes']:
            if time.monotonic()-started>900:raise RuntimeError('Render exceeded 15 minutes.')
            first=round(scene['start_s']*fps)
            last=total_frames if scene is timeline['scenes'][-1] else round(scene['end_s']*fps)
            frames=last-first
            if frames<=0:continue
            asset=media[scene['asset_id']];asset_id=asset['asset_id']
            path=Path(asset['path']);args=['ffmpeg','-nostdin','-v','error','-y']
            if asset['kind']=='image':
                if asset_id not in image_cache:
                    normalized=folder/f'{asset_id}.png'
                    with Image.open(path) as im:
                        im=ImageOps.exif_transpose(im).convert('RGB')
                        im.thumbnail((3840,3840))
                        im.save(normalized)
                    image_cache[asset_id]=normalized
                args+=['-f','image2','-loop','1','-framerate','30','-i',str(image_cache[asset_id])]
            else:
                offset=scene.get('video_in_s',video_offsets.get(asset_id,0))%asset['metadata']['duration_s']
                args+=['-protocol_whitelist','file,pipe','-f','mov','-stream_loop','-1','-ss',str(offset),'-i',str(path)]
                video_offsets[asset_id]=offset+frames/fps
            shot=folder/f'shot{len(shots):04d}.mp4'
            args+=['-an','-vf',filters(scene['effect'],width,height,frames,options['motion_amount'],options['fit_mode']),'-frames:v',str(frames),
                   '-r','30','-c:v','libx264','-threads','2','-filter_threads','1','-preset','veryfast',
                   '-crf','21','-pix_fmt','yuv420p',str(shot)]
            run_process(args,cancel)
            shots.append(shot.name)
            progress(.85*last/total_frames)
        listing=folder/'shots.txt'
        listing.write_text(''.join("file '"+name+"'\n" for name in shots),encoding='utf-8')
        overlay=folder/'caption.png'
        overlay_image(overlay,width,height,options['title'],options['caption'])
        args=['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
              '-f','concat','-safe','1','-i',str(listing),
              '-protocol_whitelist','file,pipe','-f',DEMUXERS[source.suffix.lower()],
              '-ss',str(timeline['music_in_s']),'-i',str(source),
              '-loop','1','-i',str(overlay),'-filter_complex','[0:v][2:v]overlay=0:0:shortest=1[v]',
              '-map','[v]','-map','1:a:0','-c:v','libx264','-threads','2','-filter_complex_threads','1',
              '-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
              '-t',str(duration),'-movflags','+faststart']
        if options['audio_gain_db']:
            args+=['-af',f"volume={options['audio_gain_db']}dB,alimiter=limit=0.98"]
        args.append(str(output))
        run_process(args,cancel,timeout=180)
        progress(1)
