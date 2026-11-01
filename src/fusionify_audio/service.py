"""Persistent single-owner creator workspace and bounded background jobs."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .assets import download_file, inspect_media, local_media
from .engine import analyze, decode, media_file
from .project import ProjectOptions, preview_excerpt, project_timeline
from .render import edit_plan, visualizer
from .rhythm import estimate_taps, tempo_map_beats
from .direction import music_direction
from .store import Store, identifier


class Service:
    def __init__(self, media_root: Path, state_root: Path, import_hosts: set[str]|None=None):
        self.media_root=media_root.expanduser().resolve(strict=True)
        self.state_root=state_root.expanduser().resolve()
        self.state_root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.import_hosts={h.lower().rstrip('.') for h in (import_hosts or set())}
        self._lockfile=(self.state_root/'server.lock').open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self._lockfile.write(b'0');self._lockfile.flush();self._lockfile.seek(0)
                msvcrt.locking(self._lockfile.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._lockfile.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self._lockfile.close()
            raise ValueError('This state directory is already used by another server process.') from None
        self.store=Store(self.state_root)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='fai-render')
        self.lock=threading.Lock()
        self.cancellations={}
        self.closed=False
        self.artifact_url=None
        self.upload_url=None
        for job in self.store.list('job',100):
            if job['status'] in ('queued','running','cancelling'):
                job.update(status='interrupted',error='Server restarted before this job completed.')
                self.store.put('job',job['job_id'],job)

    def workspace(self) -> dict:
        from .semantic import availability
        return {'version':'0.5.0','mode':'single-owner workspace','upload_url':self.upload_url,
                'styles':['jj','cinematic','promo','minimal'],'aspects':['9:16','16:9','1:1'],
                'url_import_hosts':sorted(self.import_hosts),'max_audio_duration_s':180,
                'semantic_audio':availability(),
                'rhythm_editing':{'tempo_regions':32,'bpm_range':[30,300],'max_snap_tolerance_s':.1,'max_manual_markers':2000},
                'music_direction':{'pacing_modes':['beat','musical'],'native_visuals':['globe','spectrum','orbit','market'],
                                   'max_story_blocks':8,'editorial_sections_are_proposals':True},
                'note':'Attachments require explicit upload. DSP timing is estimated; semantic audio is separately opt-in.'}

    def describe_audio(self, analysis_id: str, question: str, allow_external_processing: bool=False) -> dict:
        from .semantic import describe
        source,_=self._verified_audio(analysis_id)
        return describe(source,question,allow_external_processing)

    def _record_path(self, analysis_id: str) -> Path:
        return self.state_root/f'{identifier(analysis_id)}.json'

    def register_asset(self, path: str, label: str|None=None) -> dict:
        source=local_media(self.media_root,path)
        details=inspect_media(source)
        if label is not None and (not label.strip() or len(label)>160):
            raise ValueError('Asset label must contain 1 to 160 characters.')
        asset_id=uuid.uuid4().hex
        asset={'asset_id':asset_id,'filename':label or source.name,'path':str(source),**details,'created_at':time.time()}
        self.store.put('asset',asset_id,asset)
        return {k:v for k,v in asset.items() if k!='path'}

    def assets(self, limit: int=50) -> list[dict]:
        return [{k:v for k,v in a.items() if k!='path'} for a in self.store.list('asset',limit)]

    def asset(self, asset_id: str, verify: bool=False) -> dict:
        asset=self.store.get('asset',asset_id)
        source=local_media(self.media_root,asset['path'])
        if verify and hashlib.sha256(source.read_bytes()).hexdigest()!=asset['sha256']:
            raise ValueError('Asset changed since registration; register it again.')
        return asset

    def import_url(self, url: str) -> dict:
        folder=self.media_root/'imports';folder.mkdir(exist_ok=True)
        if not folder.resolve().is_relative_to(self.media_root):raise ValueError('Invalid imports directory.')
        path=download_file(url,folder,self.import_hosts)
        try:return self.register_asset(str(path))
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def analyze(self, audio_path: str) -> dict:
        if len(audio_path)==32 and all(c in '0123456789abcdef' for c in audio_path):
            asset=self.asset(audio_path,verify=True)
            if asset['kind'] not in ('audio','video'):raise ValueError('Select audio or a video with an audio track.')
            source=media_file(self.media_root,asset['path'])
        else:source=media_file(self.media_root,audio_path)
        report,_=analyze(source)
        analysis_id=uuid.uuid4().hex
        self.store.put('analysis',analysis_id,{'source_path':str(source),'report':report})
        return {'analysis_id':analysis_id,'source':report['source'],'duration_s':report['duration_s'],
                'tempo_bpm_estimate':report['tempo_bpm_estimate'],'beat_count':len(report['beats']),
                'transitions':report['transitions'],'warnings':report['warnings'],
                'next':'Inspect timing, correct beats if needed, then create a project or render a visualizer.'}

    def record(self, analysis_id: str) -> dict:
        identifier(analysis_id)
        try:return self.store.get('analysis',analysis_id)
        except ValueError:
            path=self._record_path(analysis_id)
            if not path.is_file():raise ValueError('Unknown analysis ID.') from None
            record=json.loads(path.read_text(encoding='utf-8'))
            self.store.put('analysis',analysis_id,record)
            return record

    def profile(self, analysis_id: str) -> dict:
        report=self.record(analysis_id)['report']
        return {'analysis_id':analysis_id,**{k:v for k,v in report.items() if k not in ('beats','onsets','energy','source_streams')}}

    def rhythm_review(self, analysis_id: str) -> dict:
        import numpy as np
        _, y = self._verified_audio(analysis_id)
        report = self.record(analysis_id)['report']
        # Fixed-size display data, never the full PCM signal or a source path.
        waveform = [[round(float(c.min()), 5), round(float(c.max()), 5)]
                    for c in np.array_split(y, min(1200, len(y))) if len(c)]
        return {'analysis_id':analysis_id,'duration_s':report['duration_s'],
                'time_reference':report['time_reference'],'waveform':waveform,'beats':report['beats'],
                'tempo_bpm_estimate':report['tempo_bpm_estimate'],
                'beat_provenance':report.get('beat_provenance','estimated pulse candidates'),
                'tempo_map':report.get('tempo_map',[]),'parent_analysis_id':report.get('parent_analysis_id'),
                'note':'Waveform uses equal-width min/max sample bins. Markers need listening review.'}

    @staticmethod
    def tap_tempo(tap_times_s: list[float]) -> dict:
        return estimate_taps(tap_times_s)

    def apply_tempo_map(self, analysis_id: str, regions: list[dict], snap_tolerance_s: float=0) -> dict:
        record = self.record(analysis_id)
        # Legacy analyses do not have onsets. Re-measure verified audio only when snapping is requested.
        report = record['report']
        beats, parsed = tempo_map_beats(report,regions,snap_tolerance_s)
        if snap_tolerance_s and 'onsets' not in report:
            from .engine import measure
            _, y = self._verified_audio(analysis_id)
            report = {**report,'onsets':measure(y)['onsets']}
            beats, parsed = tempo_map_beats(report,regions,snap_tolerance_s)
        new_id = uuid.uuid4().hex
        derived = {**report,'schema_version':'0.5.0','beats':beats,'tempo_map':parsed,
                   'snap_tolerance_s':snap_tolerance_s,
                   'beat_provenance':'user tempo map; snapped markers retain measured onset provenance',
                   'parent_analysis_id':analysis_id}
        self.store.put('analysis',new_id,{'source_path':record['source_path'],'report':derived})
        return {'analysis_id':new_id,'parent_analysis_id':analysis_id,'beat_count':len(beats),
                'tempo_map':parsed,'snapped_count':sum(b['provenance']=='user_grid_snapped_to_measured_onset' for b in beats),
                'note':'BPM map is a user direction, not detected tempo. Original measurements and existing projects are retained.'}

    def correct_beats(self, analysis_id: str, beat_times_s: list[float]) -> dict:
        record=self.record(analysis_id)
        duration=record['report']['duration_s']
        if not isinstance(beat_times_s,list) or len(beat_times_s)>2000:
            raise ValueError('Provide a list of at most 2000 source-relative beat times.')
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<duration for x in beat_times_s):
            raise ValueError('Beat times must be finite numbers within the audio duration.')
        if any(a>=b for a,b in zip(beat_times_s,beat_times_s[1:])):
            raise ValueError('Beat times must be unique and strictly increasing.')
        new_id=uuid.uuid4().hex
        report={k:v for k,v in record['report'].items() if k not in ('tempo_map','snap_tolerance_s')}
        report={**report,'schema_version':'0.5.0','beats':[{'time_s':float(t),'strength':1,'provenance':'user'} for t in beat_times_s],
                'beat_provenance':'user supplied; not independently verified','parent_analysis_id':analysis_id}
        self.store.put('analysis',new_id,{'source_path':record['source_path'],'report':report})
        return {'analysis_id':new_id,'parent_analysis_id':analysis_id,'beat_count':len(beat_times_s),
                'note':'Created a new analysis; existing projects retain their original timing.'}

    def timeline(self, analysis_id: str, start_s: float=0, end_s: float|None=None, limit: int=100) -> dict:
        report=self.record(analysis_id)['report']
        end_s=report['duration_s'] if end_s is None else end_s
        if not all(math.isfinite(v) for v in (start_s,end_s)) or not 0<=start_s<end_s<=report['duration_s']+.001:
            raise ValueError('Select a finite range within source duration.')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500:
            raise ValueError('Limit must be an integer from 1 to 500.')
        beats=[b for b in report['beats'] if start_s<=b['time_s']<end_s]
        energy=[e for e in report['energy'] if start_s<=e['time_s']<end_s]
        return {'analysis_id':analysis_id,'time_reference':report['time_reference'],
                'beats':beats[:limit], 'total_in_range':len(beats), 'truncated':len(beats)>limit,
                'energy':energy[:limit], 'energy_truncated':len(energy)>limit,
                'transitions':[e for e in report['transitions'] if start_s<=e['time_s']<end_s]}

    def plan(self, analysis_id: str, start_s: float=0, duration_s: float|None=None, intensity: str='medium') -> dict:
        return {'analysis_id':analysis_id,**edit_plan(self.record(analysis_id)['report'],start_s,duration_s,intensity)}

    def music_direction(self, analysis_id: str, start_s: float=0, duration_s: float|None=None,
                        intensity: str='medium', section_count: int=5, content_brief: str='',
                        section_anchors: list[dict]|None=None) -> dict:
        result=music_direction(self.record(analysis_id)['report'],start_s,duration_s,intensity,section_count,content_brief,section_anchors)
        # Full accent timestamps are already accessible through the audio timeline/review tools.
        return {'analysis_id':analysis_id,**{k:v for k,v in result.items() if k!='accents'}}

    def _validate_options(self, analysis_id: str, options: dict) -> tuple[dict,dict]:
        parsed=ProjectOptions.model_validate(options)
        for aid in parsed.asset_ids:
            if self.asset(aid)['kind'] not in ('image','video'):raise ValueError('Montage assets must be images or video.')
        for scene in parsed.scene_overrides:
            asset=self.asset(scene.asset_id)
            if asset['kind']=='video' and scene.video_in_s>=asset['metadata']['duration_s']:
                raise ValueError('Video in-point must be within the selected clip.')
            if asset['kind']=='image' and scene.video_in_s:
                raise ValueError('An image cannot have a video in-point.')
        timeline=project_timeline(self.record(analysis_id)['report'],parsed)
        return parsed.model_dump(),timeline

    def create_project(self, analysis_id: str, options: dict|None=None) -> dict:
        opts,timeline=self._validate_options(analysis_id,options or {})
        project_id=uuid.uuid4().hex
        project={'project_id':project_id,'revision':1,'analysis_id':analysis_id,'options':opts,'timeline':timeline}
        self.store.put('project',project_id,project)
        return project

    def project(self, project_id: str) -> dict:
        return self.store.get('project',project_id)

    def content_fit(self, project_id: str) -> dict:
        project=self.project(project_id);options=ProjectOptions.model_validate(project['options'])
        timeline=project['timeline'];scenes=timeline['scenes'];duration=timeline['duration_s'];flags=[]
        media=[self.asset(aid) for aid in options.asset_ids]
        videos=[a for a in media if a['kind']=='video']
        if duration>=8 and len(scenes)/duration>1/1.5:
            flags.append({'code':'rapid_scene_changes','suggestion':'Use musical pacing or longer explicit scenes; reserve ordinary beats for small movements.'})
        if videos and options.text_overlay:
            flags.append({'code':'check_existing_text','suggestion':'Inspect supplied footage for existing titles. Disable text_overlay when it is already composed.'})
        if videos and any(a['kind']=='image' for a in media) and options.video_playback=='continue':
            flags.append({'code':'footage_clock_may_drift','suggestion':'For footage already synchronized to this soundtrack, use source_sync or explicit source in-points.'})
        for video in videos:
            allocated=[s for s in scenes if s['asset_id']==video['asset_id']]
            used=sum(s['end_s']-s['start_s'] for s in allocated)
            length=video['metadata']['duration_s']
            synced_end=max((s.get('video_in_s',timeline['music_in_s']+s['start_s'])+s['end_s']-s['start_s'] for s in allocated),default=0)
            explicit_end=max((s['video_in_s']+s['end_s']-s['start_s'] for s in allocated if 'video_in_s' in s),default=0)
            if (synced_end if options.video_playback=='source_sync' else max(used,explicit_end))>length+.01:
                flags.append({'code':'short_clip_loops','asset_id':video['asset_id'],
                              'suggestion':'This clip may loop. Use longer footage, fewer allocated seconds or native motion graphics when loops would break the story.'})
        direction=timeline.get('music_direction')
        if direction and not direction['accents']:
            flags.append({'code':'no_pulse_accents','suggestion':'No pulse accents are available. Keep intentional continuous movement; do not invent beat synchronization.'})
        return {'project_id':project_id,'revision':project['revision'],'status':'needs_review' if flags else 'no_structural_flags',
                'content_brief':options.content_brief,'duration_s':duration,'scene_count':len(scenes),
                'accent_count':direction['accent_count'] if direction else len(timeline['events']),
                'flags':flags,'illustration_note':'Native market graphics use audio amplitudes, not business or financial data.',
                'note':'Structural checks do not establish semantic content fit or perceptual synchronization. Inspect visuals and listen before publishing.'}

    def list_projects(self, limit: int=50) -> list[dict]:
        return [{k:v for k,v in p.items() if k!='timeline'} | {'duration_s':p['timeline']['duration_s'],
                'scene_count':len(p['timeline']['scenes'])} for p in self.store.list('project',limit)]

    def list_jobs(self, limit: int=50) -> list[dict]:
        return [self.status(j['job_id']) for j in self.store.list('job',limit)]

    def revise_project(self, project_id: str, expected_revision: int, changes: dict) -> dict:
        if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision<1:
            raise ValueError('Expected revision must be a positive integer.')
        current=self.project(project_id)
        opts,timeline=self._validate_options(current['analysis_id'],{**current['options'],**changes})
        return self.store.revise(project_id,expected_revision,{'options':opts,'timeline':timeline})

    def _queue(self, kind: str, spec: dict, worker, suffix: str='mp4') -> dict:
        with self.lock:
            if self.closed:raise ValueError('Workspace is closing.')
            active=[j for j in self.store.list('job',100) if j['status'] in ('queued','running','cancelling')]
            if len(active)>=4:raise ValueError('Render queue is full; wait or cancel a job.')
            job_id=uuid.uuid4().hex
            cancel=threading.Event();self.cancellations[job_id]=cancel
            job={'job_id':job_id,'kind':kind,'format':suffix,'spec':spec,'status':'queued','progress':0,'created_at':time.time()}
            job.update({k:spec[k] for k in ('project_id','revision','preview','preview_start_s','preview_duration_s') if k in spec})
            self.store.put('job',job_id,job)
        def update(**values):
            with self.lock:
                current=self.store.get('job',job_id)
                self.store.put('job',job_id,{**current,**values})
        def work():
            if cancel.is_set():
                with self.lock:self.cancellations.pop(job_id,None)
                return
            update(status='running')
            output=self.state_root/f'{job_id}.{suffix}'
            try:
                worker(output,cancel,lambda value:update(progress=round(value,3)))
                if cancel.is_set():
                    output.unlink(missing_ok=True);update(status='cancelled')
                else:update(status='completed',progress=1,output_path=str(output))
            except Exception as exc:
                output.unlink(missing_ok=True)
                update(status='cancelled' if cancel.is_set() else 'failed',error=str(exc))
            finally:
                with self.lock:self.cancellations.pop(job_id,None)
        self.pool.submit(work)
        return {'job_id':job_id,'status':'queued','next':'Poll get_job_status for completion, errors, or the resulting artifact.',
                **{k:job[k] for k in ('project_id','revision','preview','preview_start_s','preview_duration_s') if k in job}}

    def _verified_audio(self, analysis_id: str):
        record=self.record(analysis_id)
        source=media_file(self.media_root,record['source_path'])
        expected=record['report']['source']['sha256']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise ValueError('Source changed since analysis; analyze it again.')
        y,_=decode(source)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise ValueError('Source changed since analysis; analyze it again.')
        return source,y

    def render(self, analysis_id: str, title: str='Your sound. In motion.', start_s: float=0,
               duration_s: float|None=None, intensity: str='medium') -> dict:
        if not 1<=len(title)<=80:raise ValueError('Title must contain 1 to 80 characters.')
        plan=self.plan(analysis_id,start_s,duration_s,intensity)
        def worker(output,cancel,progress):
            source,y=self._verified_audio(analysis_id)
            visualizer(source,y,plan,output,title,cancel,progress)
        return self._queue('visualizer',{'analysis_id':analysis_id,'plan':plan,'title':title},worker)

    def render_project(self, project_id: str, preview: bool=False, preview_start_s: float=0,
                       preview_duration_s: float|None=None) -> dict:
        if not isinstance(preview,bool):raise ValueError('Preview must be a boolean.')
        if isinstance(preview_start_s,bool) or not isinstance(preview_start_s,(int,float)) or not math.isfinite(preview_start_s):
            raise ValueError('Preview start must be a finite number.')
        if not preview and (preview_start_s!=0 or preview_duration_s is not None):
            raise ValueError('Preview range parameters require preview=true; final renders preserve the full saved project.')
        project=self.project(project_id)
        options,timeline=self._validate_options(project['analysis_id'],dict(project['options']))
        media={aid:self.asset(aid,verify=True) for aid in options['asset_ids']}
        if preview:
            timeline=preview_excerpt(timeline,options,media,preview_start_s,preview_duration_s)
            options['resolution']=480
            options['duration_s']=timeline['duration_s']
        def worker(output,cancel,progress):
            source,y=self._verified_audio(project['analysis_id'])
            if options['visual_mode']=='motion_graphics':
                from .motion import render_motion
                render_motion(source,y,timeline,options,output,cancel,progress)
            elif media:
                from .montage import montage
                verified={aid:self.asset(aid,verify=True) for aid in media}
                montage(source,timeline,options,verified,output,cancel,progress)
            else:
                visualizer(source,y,timeline,output,options['title'],cancel,progress)
        return self._queue('project',{'project_id':project_id,'revision':project['revision'],'preview':preview,
                                      'preview_start_s':preview_start_s if preview else None,
                                      'preview_duration_s':timeline['duration_s'] if preview else None,
                                      'options':options,'timeline':timeline},worker)

    def status(self, job_id: str) -> dict:
        job=self.store.get('job',job_id)
        result={k:v for k,v in job.items() if k!='spec'}
        if job['status']=='completed' and self.artifact_url:
            result.pop('output_path',None)
            result['download_url']=self.artifact_url(job_id,job.get('format','mp4'))
        return result

    def cancel_job(self, job_id: str) -> dict:
        with self.lock:
            job=self.store.get('job',job_id)
            if job['status'] in ('queued','running','cancelling'):
                event=self.cancellations.get(job_id)
                if event:event.set()
                job['status']='cancelled' if job['status']=='queued' else 'cancelling'
                self.store.put('job',job_id,job)
        return self.status(job_id)

    def export(self, project_id: str, format: str='json') -> dict:
        project=self.project(project_id)
        if format not in ('json','csv'):raise ValueError('Export format must be json or csv.')
        artifact_id=uuid.uuid4().hex
        output=self.state_root/f'{artifact_id}.{format}'
        if format=='json':output.write_text(json.dumps(project,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        else:
            stream=io.StringIO();writer=csv.writer(stream)
            writer.writerow(['scene','video_start_s','video_end_s','music_start_s','effect','asset_id'])
            for i,s in enumerate(project['timeline']['scenes']):
                writer.writerow([i+1,s['start_s'],s['end_s'],round(s['start_s']+project['timeline']['music_in_s'],5),s['effect'],s['asset_id'] or ''])
            output.write_text(stream.getvalue(),encoding='utf-8')
        result={'artifact_id':artifact_id,'format':format,'project_id':project_id,'revision':project['revision']}
        self.store.put('artifact',artifact_id,{'path':str(output),'format':format})
        if self.artifact_url:result['download_url']=self.artifact_url(artifact_id,format)
        else:result['output_path']=str(output)
        return result

    def artifact_path(self, artifact_id: str, suffix: str) -> Path:
        identifier(artifact_id)
        if suffix in ('mp4','mp3'):
            job=self.store.get('job',artifact_id)
            if job['status']!='completed':raise ValueError('Artifact is not ready.')
            if job.get('format','mp4')!=suffix:raise ValueError('Artifact format mismatch.')
            path=Path(job['output_path'])
        elif suffix in ('json','csv','svg'):
            item=self.store.get('artifact',artifact_id)
            if item['format']!=suffix:raise ValueError('Artifact format mismatch.')
            path=Path(item['path'])
        else:raise ValueError('Unknown artifact format.')
        path=path.resolve(strict=True)
        if not path.is_relative_to(self.state_root) or not path.is_file():raise ValueError('Invalid artifact.')
        return path

    def beat_preview(self, analysis_id: str, start_s: float=0, duration_s: float|None=None, click_volume: float=1) -> dict:
        if isinstance(click_volume,bool) or not isinstance(click_volume,(int,float)) or not math.isfinite(click_volume) or not 0<=click_volume<=2:
            raise ValueError('Click volume must be a finite number from 0 to 2; zero previews original music.')
        plan=self.plan(analysis_id,start_s,duration_s,'high')
        def worker(output,cancel,progress):
            import numpy as np
            import tempfile
            from scipy.io import wavfile
            from .engine import SR,DEMUXERS
            from .montage import run_process
            source,_=self._verified_audio(analysis_id)
            duration=plan['duration_s'];samples=np.zeros(math.ceil(duration*SR),dtype=np.float32)
            tx=np.arange(round(.025*SR))/SR
            tone=(click_volume*.12*np.sin(2*np.pi*1800*tx)*np.exp(-tx*150)).astype(np.float32)
            for e in plan['events']:
                k=round(e['video_time_s']*SR);count=min(len(tone),len(samples)-k)
                if count>0:samples[k:k+count]+=tone[:count]
            with tempfile.TemporaryDirectory(dir=self.state_root) as temp:
                clicks=Path(temp)/'clicks.wav';wavfile.write(clicks,SR,samples)
                run_process(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
                    '-f',DEMUXERS[source.suffix.lower()],'-ss',str(start_s),'-i',str(source),'-i',str(clicks),
                    '-filter_complex',f'[0:a]volume={0.78 if click_volume else 1}[a];[a][1:a]amix=inputs=2:duration=shortest:normalize=0[out]',
                    '-map','[out]','-t',str(duration),'-c:a','libmp3lame','-b:a','160k',str(output)],cancel)
            progress(1)
        return self._queue('beat-preview',{'analysis_id':analysis_id,'plan':plan,'click_volume':click_volume},worker,suffix='mp3')

    def export_analysis(self, analysis_id: str, format: str='json') -> dict:
        if format not in ('json','svg'):raise ValueError('Analysis export format must be json or svg.')
        report=self.record(analysis_id)['report'];artifact_id=uuid.uuid4().hex
        path=self.state_root/f'{artifact_id}.{format}'
        if format=='json':path.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        else:
            import numpy as np
            from xml.sax.saxutils import escape
            _,y=self._verified_audio(analysis_id)
            envelope=[float(np.max(np.abs(c))) for c in np.array_split(y,500) if len(c)]
            points=' '.join(f'{30+i*940/max(1,len(envelope)-1):.1f},{140-v*100:.1f}' for i,v in enumerate(envelope))
            markers=''.join(f'<line x1="{30+b["time_s"]/report["duration_s"]*940:.1f}" y1="40" x2="{30+b["time_s"]/report["duration_s"]*940:.1f}" y2="240" stroke="#2164f3" opacity=".25"/>' for b in report['beats'])
            path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 280"><rect width="1000" height="280" fill="white"/><text x="30" y="25" font-family="sans-serif" font-size="15">{escape(report["source"]["filename"])} | estimated beat markers</text>{markers}<polyline points="{points}" fill="none" stroke="#142747" stroke-width="2"/><text x="30" y="267" font-family="sans-serif" font-size="13">0 s</text><text x="900" y="267" font-family="sans-serif" font-size="13">{report["duration_s"]:.2f} s</text></svg>',encoding='utf-8')
        self.store.put('artifact',artifact_id,{'path':str(path),'format':format})
        result={'artifact_id':artifact_id,'format':format}
        if self.artifact_url:result['download_url']=self.artifact_url(artifact_id,format)
        else:result['output_path']=str(path)
        return result

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
            for cancel in self.cancellations.values():cancel.set()
        self.pool.shutdown(wait=True)
        self._lockfile.close()
