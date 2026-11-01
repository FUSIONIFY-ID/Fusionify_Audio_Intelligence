"""Continuous, code-owned motion graphics driven by actual music features."""
from __future__ import annotations

import bisect
import math
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal

from .engine import DEMUXERS, SR
from .render import dimensions

INK=(13,19,24); WHITE=(240,244,237); MUTED=(137,153,159)
COLORS={'lime':(199,250,90),'blue':(100,176,255),'coral':(255,151,119)}
DEFAULT_STORY=[
    {'headline':'YOUR MUSIC. YOUR DIRECTION.','support':'Let the soundtrack set the pace.','visual':'globe'},
    {'headline':'FEEL THE MOVEMENT.','support':'A continuous composition, with room to breathe.','visual':'globe'},
    {'headline':'FOLLOW THE ENERGY.','support':'Small accents. Intentional scene changes.','visual':'orbit'},
    {'headline':'KEEP IT CONNECTED.','support':'Motion responds to the actual sound.','visual':'spectrum'},
    {'headline':'YOUR NEXT EDIT.','support':'Original music. Your visual story.','visual':'globe'},
]


@lru_cache(maxsize=96)
def font(size: int, bold: bool=False):
    try:return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',size)
    except OSError:return ImageFont.load_default(size=size)


def fit_text(text: str, width: int, height: int, size: int, bold: bool=False) -> tuple[list[str],object,int]:
    """Shrink and wrap text into a bounded slot, including long unbroken words."""
    for fs in range(max(9,size),8,-1):
        f=font(fs,bold);lines=[];line=''
        for word in text.split():
            parts=[];part=''
            for char in word:
                if f.getlength(part+char)>width and part:parts.append(part);part=''
                part+=char
            parts.append(part)
            for part in parts:
                candidate=(line+' '+part).strip()
                if f.getlength(candidate)>width and line:lines.append(line);line=part
                else:line=candidate
        if line:lines.append(line)
        leading=math.ceil(fs*1.28)
        if len(lines)*leading<=height:return lines,f,leading
    # Extreme content is clipped to the allocated text box, never painted over other content.
    return lines[:max(1,height//leading)],f,leading


class MotionFrames:
    def __init__(self, y: np.ndarray, timeline: dict, options: dict):
        self.y,self.timeline,self.options=y,timeline,options
        self.width,self.height=dimensions(options['aspect'],options['resolution'])
        self.direction=timeline['music_direction'];self.sections=self.direction['sections']
        self.boundaries=[s['start_s'] for s in self.sections]
        self.beats=[a['video_time_s'] for a in self.direction['accents']]
        strengths=np.array([a['strength'] for a in self.direction['accents']])
        self.strengths=np.clip(strengths/(np.percentile(strengths,85)+1e-8),0,1) if len(strengths) else strengths
        self.accent=COLORS[options['accent_color']]
        self.story=options['story_blocks'] or [dict(s) for s in DEFAULT_STORY]
        if not options['story_blocks']:
            self.story[0]['headline']=options['title'];self.story[-1]['headline']=options['title']
        # Story copy is laid out once. There is exactly one headline layer per scene.
        w,h=self.width,self.height;self.landscape=w>h*1.3
        self.margin=round(min(w,h)*.072)
        self.text_width=round(w*.45) if self.landscape else w-2*self.margin
        self.text_top=round(h*.24) if self.landscape else round(h*.15)
        self.text_height=round(h*.31) if self.landscape else round(h*.21)
        self.text_layout=[fit_text(s['headline'],self.text_width,self.text_height,round(min(w,h)*.095),True) for s in self.story]
        self.support_layout=[fit_text(s['support'],self.text_width,round(h*(.09 if self.landscape else .07)),round(min(w,h)*.033)) for s in self.story]
        self.brand_layout=fit_text(options['brand'],w-2*self.margin,round(h*.045),round(min(w,h)*.038),True)
        f,st,z=signal.stft(y,fs=SR,nperseg=1024,noverlap=804,boundary=None)
        edges=np.geomspace(35,9500,33)
        values=[]
        for low,high in zip(edges,edges[1:]):
            band=np.abs(z[(f>=low)&(f<high)])
            values.append(np.sqrt(np.mean(band**2,axis=0)) if len(band) else np.zeros(len(st)))
        values=np.log1p(300*np.array(values))
        self.spectrum=np.clip(values/(np.percentile(values,97,axis=1)[:,None]+1e-8),0,1)
        self.spectrum_times=st
        self.sphere=[]
        for lat in np.linspace(-np.pi/2,np.pi/2,11)[1:-1]:
            lon=np.linspace(0,2*np.pi,90)
            self.sphere.append(np.stack([np.cos(lat)*np.sin(lon),np.full(len(lon),np.sin(lat)),np.cos(lat)*np.cos(lon)],axis=1))
        for lon in np.linspace(0,np.pi,11,endpoint=False):
            lat=np.linspace(0,2*np.pi,90)
            self.sphere.append(np.stack([np.sin(lat)*np.cos(lon),np.cos(lat),np.sin(lat)*np.sin(lon)],axis=1))

    def state(self,t: float) -> dict:
        index=max(0,min(len(self.sections)-1,bisect.bisect_right(self.boundaries,t)-1))
        pos=bisect.bisect_right(self.beats,t)-1
        delta=t-self.beats[pos] if pos>=0 else 20
        pulse=math.exp(-delta*12)*self.options['motion_amount']*(float(self.strengths[pos]) if pos>=0 else 0)
        return {'section':index,'source_time_s':self.timeline['music_in_s']+t,
                'motion_clock_s':t,'pulse':pulse,'local_s':t-self.sections[index]['start_s']}

    @staticmethod
    def text(draw,position,layout,color):
        lines,f,leading=layout
        for i,line in enumerate(lines):draw.text((position[0],position[1]+i*leading),line,font=f,fill=color)

    def globe(self,draw,t,cx,cy,r,color):
        angle=t*.19*self.options['motion_amount'];tilt=-.28
        for points in self.sphere:
            x,y,z=points.T
            xx=x*np.cos(angle)+z*np.sin(angle);zz=-x*np.sin(angle)+z*np.cos(angle)
            yy=y*np.cos(tilt)-zz*np.sin(tilt);depth=y*np.sin(tilt)+zz*np.cos(tilt)
            q=np.stack([cx+r*xx*(1+.1*depth),cy+r*yy*(1+.1*depth)],axis=1)
            for i in range(len(q)-1):
                draw.line([tuple(q[i]),tuple(q[i+1])],fill=color if depth[i]>.1 else (45,62,59),width=1)

    def frame(self,t: float) -> Image.Image:
        state=self.state(t);w,h=self.width,self.height;m=self.margin
        section=state['section'];block_index=min(section,len(self.story)-1);block=self.story[block_index]
        source_t=state['source_time_s'];pulse=state['pulse'];amount=self.options['motion_amount']
        im=Image.new('RGB',(w,h),INK);d=ImageDraw.Draw(im)
        d.line((m,h*.105,w-m,h*.105),fill=(43,58,64),width=1)
        self.text(d,(m,h*.035),self.brand_layout,WHITE)
        # Project time drives all graphics. Changing sections never resets the rotation clock.
        head_y=self.text_top+round(7*math.exp(-state['local_s']*7)*amount)
        self.text(d,(m,head_y),self.text_layout[block_index],WHITE)
        self.text(d,(m,self.text_top+self.text_height+.01*h),self.support_layout[block_index],MUTED)
        cx,cy=(w*.73,h*.47) if self.landscape else (w*.5,h*.64)
        radius=min(w*.29,h*.17) if not self.landscape else h*.30
        radius*=1+.025*pulse
        feature=self.sections[section]['role']=='feature'
        graphic_color=INK if feature else self.accent
        if feature:
            pad=radius*1.10
            d.rounded_rectangle((cx-pad,cy-pad,cx+pad,cy+pad),radius=max(2,round(radius*.045)),fill=self.accent)
        spectrum_index=min(len(self.spectrum_times)-1,int(np.searchsorted(self.spectrum_times,source_t)))
        values=self.spectrum[:,spectrum_index]
        if block['visual']=='globe':
            self.globe(d,t,cx,cy,radius,graphic_color)
            d.arc((cx-radius*1.14,cy-radius*1.14,cx+radius*1.14,cy+radius*1.14),
                  start=t*20*amount,end=t*20*amount+65,fill=INK if feature else WHITE,width=max(1,round(w*.003)))
        elif block['visual']=='orbit':
            for j in range(5):
                r=radius*(.28+j*.17)*(1+.025*pulse)
                pts=[(cx+math.cos(a+t*.2*amount)*r,cy+math.sin(a+t*.2*amount)*r) for a in np.linspace(0,2*np.pi,5)]
                d.line(pts,fill=graphic_color,width=max(1,round(min(w,h)*.003)))
        elif block['visual']=='spectrum':
            for i,v in enumerate(values[::2]):
                x=cx-radius+i*radius*2/16;bar=(.06+float(v)*.84)*radius
                d.rounded_rectangle((x,cy-bar,x+radius*.075,cy+bar),radius=max(1,round(radius*.03)),fill=graphic_color if feature or i%4 else WHITE)
        else:
            # An audio-derived illustrative chart, never invented sales or financial performance.
            for j in range(4):d.line((cx-radius,cy-radius+j*radius*.6,cx+radius,cy-radius+j*radius*.6),fill=(41,56,63))
            levels=[]
            for k in range(70):
                at=source_t-3+3*k/69;sample=int(max(0,at)*SR)
                chunk=self.y[sample:min(len(self.y),sample+round(SR*.04))]
                levels.append(float(np.sqrt(np.mean(chunk*chunk))) if len(chunk) else 0)
            db=20*np.log10(np.maximum(levels,1e-8));low=float(np.percentile(db,10))-3;high=float(np.percentile(db,90))+3
            values=np.clip((db-low)/max(6,high-low),0,1) if max(levels)>1e-6 else np.zeros(len(levels))
            pts=[(cx-radius+i/69*2*radius,cy+radius*.7-float(v)*radius*1.5) for i,v in enumerate(values)]
            d.line(pts,fill=graphic_color,width=max(1,round(min(w,h)*.004)))
            label=fit_text('AUDIO-DERIVED ILLUSTRATION',round(radius*2),round(h*.055),round(min(w,h)*.021))
            self.text(d,(cx-radius,cy+radius*.82),label,INK if feature else MUTED)
        # Genuine audio waveform; the decorative graphic never substitutes for measured timing.
        center=round(source_t*SR);ix=np.linspace(center-SR//2,center+SR//2,260).astype(int)
        wave=self.y[np.clip(ix,0,len(self.y)-1)]
        d.line([(m+i*(w-2*m)/259,h*.86+float(v)*min(w,h)*.065) for i,v in enumerate(wave)],fill=self.accent,width=max(1,round(min(w,h)*.003)))
        small=font(max(9,round(min(w,h)*.022)))
        d.text((m,h*.915),f'MUSIC-DRIVEN / {section+1:02d}',font=small,fill=MUTED)
        time_label=f'{t:05.2f} / {self.timeline["duration_s"]:05.2f} s'
        d.text((w-m,h*.915),time_label,font=small,fill=MUTED,anchor='ra')
        d.line((m,h*.957,w-m,h*.957),fill=(43,58,64),width=2)
        d.line((m,h*.957,m+(w-2*m)*min(1,t/self.timeline['duration_s']),h*.957),fill=self.accent,width=2)
        return im


def render_motion(source: Path,y: np.ndarray,timeline: dict,options: dict,output: Path,cancel,progress):
    renderer=MotionFrames(y,timeline,options);w,h=renderer.width,renderer.height
    duration=timeline['duration_s'];frames=max(1,math.ceil(duration*30));started=time.monotonic()
    cmd=['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r','30','-i','pipe:0',
         '-protocol_whitelist','file,pipe','-f',DEMUXERS[source.suffix.lower()],'-ss',str(timeline['music_in_s']),'-i',str(source),
         '-map','0:v:0','-map','1:a:0','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart']
    if options['audio_gain_db']:cmd+=['-af',f"volume={options['audio_gain_db']}dB,alimiter=limit=0.98"]
    cmd.append(str(output))
    with output.with_suffix('.log').open('wb') as logs:
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=logs)
        try:
            for k in range(frames):
                if cancel.is_set():raise RuntimeError('Render cancelled.')
                if time.monotonic()-started>900:raise RuntimeError('Render exceeded 15 minutes.')
                p.stdin.write(renderer.frame(k/30).tobytes())
                if k%30==0:progress(.96*k/frames)
            p.stdin.close()
            if p.wait(timeout=60):raise RuntimeError('Motion graphics encoding failed; inspect the local job log.')
        except BaseException:
            if p.poll() is None:p.kill()
            p.wait();output.unlink(missing_ok=True)
            raise
    progress(1)
