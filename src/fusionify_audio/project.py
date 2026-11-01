"""Strict, declarative edit options and render timelines."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .render import edit_plan


class SceneOverride(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    start_s: float=Field(ge=0)
    end_s: float=Field(gt=0)
    asset_id: str=Field(pattern=r'^[a-f0-9]{32}$')
    effect: Literal['cut','zoom','pan','shake']='cut'
    video_in_s: float=Field(default=0,ge=0,le=180)


class ProjectOptions(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    title: str=Field(default='Your sound. In motion.',min_length=1,max_length=80)
    caption: str=Field(default='',max_length=160)
    style: Literal['jj','cinematic','promo','minimal']='jj'
    intensity: Literal['low','medium','high']='medium'
    aspect: Literal['9:16','16:9','1:1']='9:16'
    resolution: Literal[480,720,1080]=720
    music_in_s: float=Field(default=0,ge=0)
    duration_s: float|None=Field(default=None,gt=0,le=180)
    asset_ids: list[str]=Field(default_factory=list,max_length=16)
    audio_gain_db: float=Field(default=0,ge=-18,le=6)
    motion_amount: float=Field(default=.6,ge=0,le=1)
    fit_mode: Literal['cover','contain']='cover'
    scene_overrides: list[SceneOverride]=Field(default_factory=list,max_length=720)


def project_timeline(report: dict, options: ProjectOptions) -> dict:
    plan=edit_plan(report,options.music_in_s,options.duration_s,options.intensity)
    min_gap={'jj':.25,'cinematic':1.5,'promo':.8,'minimal':2.0}[options.style]
    candidates=[]
    last=0.0
    for event in plan['events']:
        t=event['video_time_s']
        if t-last>=min_gap and plan['duration_s']-t>=min_gap:
            candidates.append(t);last=t
    # No reliable pulse means a continuous scene; do not fabricate beat events.
    editorial_fallback=False
    if options.asset_ids and len(candidates)+1<len(options.asset_ids):
        if plan['duration_s']*30<len(options.asset_ids):
            raise ValueError('Audio is too short to show every selected asset for at least one frame.')
        candidates=[plan['duration_s']*i/len(options.asset_ids) for i in range(1,len(options.asset_ids))]
        editorial_fallback=True
    points=[0.0,*candidates,plan['duration_s']]
    effects={'jj':['zoom','cut','shake','pan'],'cinematic':['pan','zoom'],
             'promo':['zoom','pan','cut'],'minimal':['cut']}
    scenes=[]
    for i,(start,end) in enumerate(zip(points,points[1:])):
        scenes.append({'start_s':start,'end_s':end,
                       'asset_id':options.asset_ids[i%len(options.asset_ids)] if options.asset_ids else None,
                       'effect':effects[options.style][i%len(effects[options.style])]})
    if options.scene_overrides:
        scenes=[s.model_dump() for s in options.scene_overrides]
        previous=0
        for scene in scenes:
            if scene['asset_id'] not in options.asset_ids:raise ValueError('Override assets must be selected in asset_ids.')
            if abs(scene['start_s']-previous)>.0001 or scene['end_s']<=scene['start_s']:
                raise ValueError('Override scenes must be contiguous, ordered, and start at zero.')
            if round(scene['end_s']*30)<=round(scene['start_s']*30):raise ValueError('Each scene must occupy at least one output frame.')
            previous=scene['end_s']
        if abs(previous-plan['duration_s'])>.0001:raise ValueError('Override scenes must cover the entire selected duration.')
    return {**plan,'schema_version':'0.2.0','style':options.style,'scenes':scenes,
            'caption':options.caption,'audio_gain_db':options.audio_gain_db,
            'motion_amount':options.motion_amount,'fit_mode':options.fit_mode,
            'scene_boundary_source':'user overrides' if options.scene_overrides else 'editorial equal split (insufficient beat candidates)' if editorial_fallback else 'estimated beat candidates',
            'aspect':options.aspect,'resolution':options.resolution,
            'note':'Scene boundaries are source-derived candidates. Frame rounding applies during rendering.'}
