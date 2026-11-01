"""Strict, declarative edit options and render timelines."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .render import edit_plan
from .direction import music_direction


class StoryBlock(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    headline: str=Field(min_length=1,max_length=80)
    support: str=Field(default='',max_length=140)
    visual: Literal['globe','spectrum','orbit','market']='globe'


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
    pacing_mode: Literal['beat','musical']='beat'
    visual_mode: Literal['auto','motion_graphics']='auto'
    text_overlay: bool=True
    video_playback: Literal['continue','source_sync']='continue'
    brand: str=Field(default='FUSIONIFY',min_length=1,max_length=40)
    accent_color: Literal['lime','blue','coral']='lime'
    content_brief: str=Field(default='',max_length=300)
    story_blocks: list[StoryBlock]=Field(default_factory=list,max_length=8)


def project_timeline(report: dict, options: ProjectOptions) -> dict:
    plan=edit_plan(report,options.music_in_s,options.duration_s,options.intensity)
    native=options.visual_mode=='motion_graphics'
    if native and (options.asset_ids or options.scene_overrides):
        raise ValueError('Motion graphics use native story blocks; do not supply footage assets or scene overrides.')
    if options.story_blocks and not native:
        raise ValueError('Story blocks require visual_mode motion_graphics.')
    direction=None
    if options.pacing_mode=='musical' or native:
        direction=music_direction(report,options.music_in_s,options.duration_s,options.intensity,
                                  max(2,len(options.story_blocks)) if options.story_blocks else 5,options.content_brief)
        if native and options.story_blocks and len(direction['sections'])<len(options.story_blocks):
            raise ValueError('Selected duration is too short for every story block. Reduce blocks, increase duration, or choose higher intensity.')
    min_gap={'jj':.25,'cinematic':1.5,'promo':.8,'minimal':2.0}[options.style]
    candidates=[]
    last=0.0
    for event in plan['events']:
        t=event['video_time_s']
        if t-last>=min_gap and plan['duration_s']-t>=min_gap:
            candidates.append(t);last=t
    if direction:
        candidates=[s['start_s'] for s in direction['sections'][1:]]
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
    return {**plan,'schema_version':'0.4.0','style':options.style,'scenes':scenes,
            'pacing_mode':'musical' if direction else 'beat','visual_mode':options.visual_mode,'music_direction':direction,
            'caption':options.caption,'audio_gain_db':options.audio_gain_db,
            'motion_amount':options.motion_amount,'fit_mode':options.fit_mode,
            'scene_boundary_source':'user overrides' if options.scene_overrides else 'editorial equal split (insufficient scene boundaries)' if editorial_fallback else 'music-assisted editorial sections' if direction else report.get('beat_provenance','estimated beat candidates'),
            'aspect':options.aspect,'resolution':options.resolution,
            'note':'Scene boundaries are source-derived candidates. Frame rounding applies during rendering.'}
