"""Music evidence plus editorial pacing. No inferred chorus, drop or downbeat."""
from __future__ import annotations

import math
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .render import edit_plan
from .rhythm import Number


class SectionAnchor(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    section_index: StrictInt=Field(ge=1,le=7)
    source_time_s: Number=Field(ge=0,le=180)


def music_direction(report: dict, start_s: float=0, duration_s: float|None=None,
                    intensity: str='medium', section_count: int=5, content_brief: str='',
                    section_anchors: list[dict]|None=None) -> dict:
    plan = edit_plan(report,start_s,duration_s,intensity)
    if isinstance(section_count,bool) or not isinstance(section_count,int) or not 2<=section_count<=8:
        raise ValueError('Section count must be an integer from 2 to 8.')
    if not isinstance(content_brief,str) or len(content_brief)>300:
        raise ValueError('Content brief must contain at most 300 characters.')
    duration=plan['duration_s'];end_s=start_s+duration
    # Readable holds, independent from the number of pulse accents.
    minimum={'low':4.0,'medium':3.0,'high':2.0}[intensity]
    count=min(section_count,max(1,int(duration/minimum)))
    if section_anchors is None:section_anchors=[]
    if not isinstance(section_anchors,list) or len(section_anchors)>7:
        raise ValueError('Supply at most seven ordered section anchors.')
    anchors=[SectionAnchor.model_validate(a).model_dump() for a in section_anchors]
    hold=min(minimum,duration/count*.7)
    locks=[(0,0.0)]
    for anchor in anchors:
        index=anchor['section_index'];t=anchor['source_time_s']-start_s
        if index>=count or not 0<t<duration:
            raise ValueError('Anchor index must identify an existing later section, and time must be inside the selected source range.')
        previous_index,previous_time=locks[-1]
        if index<=previous_index or t<=previous_time:
            raise ValueError('Anchors must be unique and strictly ordered by section index and source time.')
        locks.append((index,float(t)))
    locks.append((count,duration))
    if any(b-a<(j-i)*hold-1e-7 for (i,a),(j,b) in zip(locks,locks[1:])):
        raise ValueError('Anchors leave insufficient reading time. Move an anchor, reduce sections, or explicitly choose faster intensity.')
    beats=[b for b in report['beats'] if start_s<=b['time_s']<end_s]
    rises=[t for t in report.get('transitions',[]) if start_s<t['time_s']<end_s]
    boundaries=[{'video_time_s':0.0,'evidence':'project start','locked':False}]
    for (left_index,_),(right_index,right_time) in zip(locks,locks[1:]):
        for boundary_index in range(left_index+1,right_index):
            previous=boundaries[-1]['video_time_s'];remaining=right_index-boundary_index
            span=(right_time-previous)/(remaining+1);target=previous+span;radius=span*.5;choices=[]
            for rise in rises:
                t=rise['time_s']-start_s
                if abs(t-target)<=radius and t-previous>=hold and right_time-t>=remaining*hold:
                    choices.append((0,abs(t-target),t,'measured energy rise candidate'))
            for beat in beats:
                t=beat['time_s']-start_s
                if abs(t-target)<=min(radius,.3) and t-previous>=hold and right_time-t>=remaining*hold:
                    label='user-directed marker' if beat.get('provenance','').startswith('user') else 'estimated pulse candidate'
                    choices.append((1,abs(t-target),t,label))
            if choices:_,_,t,evidence=min(choices)
            else:t,evidence=float(target),'editorial spacing; no matching audio event'
            boundaries.append({'video_time_s':round(t,5),'evidence':evidence,'locked':False})
        boundaries.append({'video_time_s':right_time,'evidence':'project end' if right_index==count else 'user source-time anchor',
                           'locked':right_index!=count})
    roles=['opening']+['development']*max(0,count-2)+(['closing'] if count>1 else [])
    if count>=4:roles[count//2]='feature'
    sections=[]
    for i,(a,b) in enumerate(zip(boundaries,boundaries[1:])):
        source_start=start_s+a['video_time_s'];source_end=start_s+b['video_time_s']
        levels=[e['rms_dbfs'] for e in report['energy'] if source_start<=e['time_s']<source_end]
        mean_db=None if not levels else round(float(10*np.log10(np.mean(10**(np.array(levels)/10))+1e-24)),2)
        sections.append({'index':i,'role':roles[i],'start_s':a['video_time_s'],'end_s':b['video_time_s'],
                         'source_start_s':round(source_start,5),'source_end_s':round(source_end,5),
                         'boundary_evidence':a['evidence'],'boundary_locked':a['locked'],'mean_rms_dbfs':mean_db,
                         'direction':'Hold the composition; use small audio reactions between editorial changes.'})
    accents=[];last=-math.inf
    for b in beats:
        t=b['time_s']-start_s
        if t-last<.12:continue
        accents.append({'video_time_s':round(t,5),'source_time_s':b['time_s'],
                        'strength':b['strength'],'provenance':b.get('provenance','estimated_pulse'),
                        'action':'micro_motion'})
        last=t
    return {'schema_version':'0.5.0','music_in_s':start_s,'duration_s':duration,'content_brief':content_brief,
            'section_anchors':anchors,'strength_reference':float(np.percentile([a['strength'] for a in accents],85)) if accents else 1,
            'sections':sections,'accents':accents,'accent_count':len(accents),
            'beat_provenance':report.get('beat_provenance','estimated pulse candidates'),
            'note':'Section roles and spacing are editorial proposals. Audio event matches are candidates, not musical structure ground truth. No automatic bar/downbeat detection.',
            'warnings':report['warnings']}
