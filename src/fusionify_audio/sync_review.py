"""Read-only scene timing evidence. Proximity is not perceptual synchronization."""
from __future__ import annotations

import bisect
import math


def review_music_sync(project: dict, report: dict, tolerance_ms: float=80,
                      offset: int=0, limit: int=100) -> dict:
    if (isinstance(tolerance_ms,bool) or not isinstance(tolerance_ms,(int,float))
            or not math.isfinite(tolerance_ms) or not 0<=tolerance_ms<=250):
        raise ValueError('Tolerance must be a finite number from 0 to 250 milliseconds.')
    if (isinstance(offset,bool) or not isinstance(offset,int) or offset<0
            or isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100):
        raise ValueError('Offset must be a nonnegative integer and limit must be 1 to 100.')
    timeline=project['timeline'];options=project['options']
    start=timeline['music_in_s'];duration=timeline['duration_s'];end=start+duration;fps=30
    native=options.get('visual_mode','auto')=='motion_graphics'
    renderer='motion_graphics' if native else 'montage' if options.get('asset_ids') else 'visualizer'
    beats=sorted((b for b in report['beats'] if start<=b['time_s']<end),key=lambda b:b['time_s'])
    rises=sorted((e for e in report.get('transitions',[]) if start<=e['time_s']<end),key=lambda e:e['time_s'])
    beat_times=[b['time_s'] for b in beats];rise_times=[e['time_s'] for e in rises]

    def nearest(events,times,source_time,kind):
        if not events:return None
        pos=bisect.bisect_left(times,source_time)
        index=min({max(0,pos-1),min(len(events)-1,pos)},key=lambda i:(abs(times[i]-source_time),times[i]))
        event=events[index];time=event['time_s']
        return {'kind':kind,'source_time_s':time,'video_time_s':time-start,
                'offset_ms':round((source_time-time)*1000,6),
                'provenance':event.get('provenance',report.get('beat_provenance','estimated pulse candidate'))
                             if kind=='pulse' else 'measured energy rise candidate'}

    sections={s['start_s']:s for s in (timeline.get('music_direction') or {}).get('sections',[])}
    boundaries=[];total_frames=max(1,math.ceil(duration*fps))
    scenes=(timeline['music_direction']['sections'] if native else timeline['scenes']) if renderer!='visualizer' else []
    for i,scene in enumerate(scenes):
        requested=scene['start_s']
        # Native section selection uses t=k/30. Montage starts each surviving shot at round(start*30).
        frame=math.ceil(requested*fps) if native else round(requested*fps)
        last=total_frames if i==len(scenes)-1 else (math.ceil(scene['end_s']*fps) if native else round(scene['end_s']*fps))
        if not 0<frame<total_frames or last<=frame:continue
        video_time=frame/fps;source_time=start+video_time
        pulse=nearest(beats,beat_times,source_time,'pulse');rise=nearest(rises,rise_times,source_time,'energy_rise')
        matches=[e for e in (pulse,rise) if e is not None]
        closest=min(matches,key=lambda e:(abs(e['offset_ms']),e['source_time_s'])) if matches else None
        status=('no_reference' if closest is None else 'near_reference'
                if abs(closest['offset_ms'])<=tolerance_ms+1e-6 else 'outside_tolerance')
        section=sections.get(requested,{})
        boundaries.append({'scene_index':i,'requested_video_time_s':requested,'video_time_s':video_time,
                           'source_time_s':source_time,'frame_index':frame,
                           'frame_shift_ms':round((video_time-requested)*1000,6),
                           'user_directed':bool(options.get('scene_overrides') or section.get('boundary_locked')),
                           'boundary_evidence':section.get('boundary_evidence',timeline.get('scene_boundary_source')),
                           'nearest_pulse':pulse,'nearest_energy_rise':rise,'closest_reference':closest,
                           'candidate_status':status})
    counts={status:sum(b['candidate_status']==status for b in boundaries)
            for status in ('near_reference','outside_tolerance','no_reference')}
    # Offer listening windows, not automatic corrections. Skip already-covered boundary centers.
    previews=[]
    for b in sorted(boundaries,key=lambda b:(b['candidate_status']=='near_reference',b['video_time_s'])):
        t=b['video_time_s']
        if any(p['preview_start_s']<=t<p['preview_start_s']+p['preview_duration_s'] for p in previews):continue
        window_start=max(0,math.floor((t-2)*fps)/fps)
        previews.append({'project_id':project['project_id'],'revision':project['revision'],
                         'preview':True,'preview_start_s':window_start,
                         'preview_duration_s':min(4,duration-window_start),
                         'boundary_scene_index':b['scene_index'],'reason':b['candidate_status']})
        if len(previews)==3:break
    return {'schema_version':'0.7.0','project_id':project['project_id'],'revision':project['revision'],
            'analysis_id':project['analysis_id'],'renderer':renderer,'fps':fps,'music_in_s':start,'duration_s':duration,
            'tolerance_ms':tolerance_ms,'boundary_count':len(boundaries),'counts':counts,
            'reference_counts':{'pulse':len(beats),'energy_rise':len(rises)},
            'status':'no_scene_boundaries' if not boundaries else 'no_reference' if not beats and not rises else 'review_available',
            'boundaries':boundaries[offset:offset+limit],
            'next_offset':offset+limit if offset+limit<len(boundaries) else None,'suggested_previews':previews,
            'note':'Offsets compare saved-analysis candidates with full-render frame times. Positive means the cut is after the candidate. '
                   'Tolerance is a review setting, not an accuracy score. Editorial or user-directed cuts can be intentional. '
                   'This does not verify current source bytes, audible beat correctness, drops, downbeats, or semantic content fit. '
                   'Review the actual excerpt and current project revision before changing anything.'}
