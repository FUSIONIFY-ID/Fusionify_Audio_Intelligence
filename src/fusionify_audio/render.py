"""Bounded waveform visualizer. No execution of model-generated code."""
from __future__ import annotations

import bisect
import math
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .engine import DEMUXERS, SR


def edit_plan(report: dict, start_s: float = 0, duration_s: float | None = None,
              intensity: str = "medium") -> dict:
    if intensity not in {"low", "medium", "high"}:
        raise ValueError("Intensity must be low, medium or high.")
    if not math.isfinite(start_s) or start_s < 0 or start_s >= report['duration_s']:
        raise ValueError("Music start must be within source duration.")
    duration_s = report['duration_s']-start_s if duration_s is None else duration_s
    if not math.isfinite(duration_s) or duration_s <= 0 or start_s+duration_s > report['duration_s']+.001:
        raise ValueError("Requested range exceeds the source audio.")
    pulses = [b for b in report['beats'] if start_s <= b['time_s'] < start_s+duration_s]
    step = {"low":4, "medium":2, "high":1}[intensity]
    return {"schema_version":"0.1.0", "music_in_s":start_s, "duration_s":round(duration_s,5),
            "intensity":intensity, "flash_enabled":False,
            "events":[{"source_time_s":b['time_s'], "video_time_s":round(b['time_s']-start_s,4),
                       "effect":"cut_or_scale", "status":"candidate"} for b in pulses[::step]],
            "warnings":report['warnings'], "note":"Review candidate timings before publishing; no bar/downbeat inference."}


def dimensions(aspect: str='9:16', resolution: int=480) -> tuple[int,int]:
    if aspect not in ('9:16','16:9','1:1') or resolution not in (480,720,1080):
        raise ValueError('Unsupported aspect or resolution.')
    long=round(resolution*16/9/2)*2
    return (resolution,long) if aspect=='9:16' else (long,resolution) if aspect=='16:9' else (resolution,resolution)


def visualizer(source: Path, y: np.ndarray, plan: dict, output: Path, title: str,
               cancel=None, progress=None) -> None:
    if not 1 <= len(title) <= 80:
        raise ValueError("Title must contain 1 to 80 characters.")
    w,h = dimensions(plan.get('aspect','9:16'),plan.get('resolution',480))
    fps=30
    margin=round(min(w,h)*.067)
    try:
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf",round(min(w,h)*.071))
        small = ImageFont.truetype("DejaVuSans.ttf",round(min(w,h)*.034))
    except OSError:
        bold, small = ImageFont.load_default(size=34), ImageFont.load_default(size=16)
    duration = plan['duration_s']; offset = plan['music_in_s']
    events = [e['video_time_s'] for e in plan['events']]
    cmd = ['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}',
           '-r',str(fps),'-i','pipe:0','-protocol_whitelist','file,pipe','-f',DEMUXERS[source.suffix.lower()],
           '-ss',str(offset),'-i',str(source),'-map','0:v:0','-map','1:a:0','-c:v','libx264',
           '-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
           '-t',str(duration),'-movflags','+faststart']
    if plan.get('audio_gain_db',0):
        cmd+=['-af',f"volume={float(plan['audio_gain_db'])}dB,alimiter=limit=0.98"]
    cmd.append(str(output))
    with output.with_suffix('.log').open('wb') as logs:
        process = subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=logs)
        try:
            frames=max(1,math.ceil(duration*fps));started=time.monotonic()
            for k in range(frames):
                if cancel is not None and cancel.is_set():raise RuntimeError('Render cancelled.')
                if time.monotonic()-started>900:raise RuntimeError('Render exceeded 15 minutes.')
                t=k/fps
                pos=bisect.bisect_right(events,t)-1
                pulse=math.exp(-14*(t-events[pos])) if pos>=0 else 0
                im=Image.new('RGB',(w,h),(12,17,24));d=ImageDraw.Draw(im)
                d.text((margin,h*.045),'FUSIONIFY',font=small,fill=(170,190,207))
                # Wrap user-provided title to keep it within frame.
                words=title.split(); lines=[]; line=''
                for word in words:
                    trial=(line+' '+word).strip()
                    if d.textbbox((0,0),trial,font=bold)[2]>w-2*margin and line:
                        lines.append(line);line=word
                    else:line=trial
                lines.append(line)
                for j,line in enumerate(lines[:3]):
                    fs=bold
                    if d.textbbox((0,0),line,font=fs)[2]>w-2*margin:
                        while line and d.textbbox((0,0),line+'…',font=fs)[2]>w-2*margin:
                            line=line[:-1]
                        line+='…'
                    d.text((margin,h*.13+j*min(w,h)*.092),line,font=fs,fill=(243,247,251))
                radius=min(w,h)*(.225+.025*pulse*plan.get('motion_amount',.6));cx,cy=w//2,h*.53
                d.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(78,165,255),width=4)
                center=int((offset+t)*SR)
                indices=np.linspace(center-SR//2,center+SR//2,190).astype(int)
                values=y[np.clip(indices,0,len(y)-1)]
                points=[(margin+i*(w-2*margin)/189,cy+float(v)*min(w,h)*.31) for i,v in enumerate(values)]
                d.line(points,fill=(203,241,255),width=2)
                caption=plan.get('caption') or 'YOUR MUSIC. IN MOTION.'
                while caption and d.textbbox((0,0),caption,font=small)[2]>w-2*margin:caption=caption[:-1]
                d.text((margin,h*.79),caption,font=small,fill=(170,190,207))
                d.text((margin,h*.84),f'{t:05.2f} / {duration:05.2f} s',font=small,fill=(243,247,251))
                d.rectangle((margin,h*.92,w-margin,h*.92+3),fill=(40,53,67))
                d.rectangle((margin,h*.92,margin+(w-2*margin)*min(t/duration,1),h*.92+3),fill=(78,165,255))
                process.stdin.write(im.tobytes())
                if progress is not None and k%30==0:progress(.95*k/frames)
            process.stdin.close()
            if process.wait(timeout=60):
                raise RuntimeError('FFmpeg render failed. Inspect the local job log.')
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            output.unlink(missing_ok=True)
            raise
