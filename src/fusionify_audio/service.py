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
from .engine import analyze, media_file
from .project import ProjectOptions, project_timeline
from .render import edit_plan, visualizer
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
        return {'version':'0.2.0','mode':'single-owner workspace','upload_url':self.upload_url,
                'styles':['jj','cinematic','promo','minimal'],'aspects':['9:16','16:9','1:1'],
                'url_import_hosts':sorted(self.import_hosts),'max_audio_duration_s':180,
                'semantic_audio':availability(),
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
        return {'analysis_id':analysis_id,**{k:v for k,v in report.items() if k not in ('beats','energy','source_streams')}}

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
        report={**record['report'],'beats':[{'time_s':float(t),'strength':1,'provenance':'user'} for t in beat_times_s],
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
        return {'job_id':job_id,'status':'queued','next':'Poll get_job_status for completion, errors, or the resulting artifact.'}

    def _verified_audio(self, analysis_id: str):
        record=self.record(analysis_id)
        source=media_file(self.media_root,record['source_path'])
        report,y=analyze(source)
        if report['source']['sha256']!=record['report']['source']['sha256']:
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

    def render_project(self, project_id: str, preview: bool=False) -> dict:
        project=self.project(project_id)
        options=dict(project['options'])
        if preview:
            options['resolution']=480
            options['duration_s']=min(project['timeline']['duration_s'],8)
            if options['scene_overrides']:
                options['scene_overrides']=[{**scene,'end_s':min(scene['end_s'],options['duration_s'])}
                    for scene in options['scene_overrides'] if scene['start_s']<options['duration_s']]
        _,timeline=self._validate_options(project['analysis_id'],options)
        media={aid:self.asset(aid,verify=True) for aid in options['asset_ids']}
        def worker(output,cancel,progress):
            source,y=self._verified_audio(project['analysis_id'])
            if media:
                from .montage import montage
                verified={aid:self.asset(aid,verify=True) for aid in media}
                montage(source,timeline,options,verified,output,cancel,progress)
            else:
                visualizer(source,y,timeline,output,options['title'],cancel,progress)
        return self._queue('project',{'project_id':project_id,'revision':project['revision'],'preview':preview,
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

    def beat_preview(self, analysis_id: str, start_s: float=0, duration_s: float|None=None) -> dict:
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
            tone=(.12*np.sin(2*np.pi*1800*tx)*np.exp(-tx*150)).astype(np.float32)
            for e in plan['events']:
                k=round(e['video_time_s']*SR);count=min(len(tone),len(samples)-k)
                if count>0:samples[k:k+count]+=tone[:count]
            with tempfile.TemporaryDirectory(dir=self.state_root) as temp:
                clicks=Path(temp)/'clicks.wav';wavfile.write(clicks,SR,samples)
                run_process(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
                    '-f',DEMUXERS[source.suffix.lower()],'-ss',str(start_s),'-i',str(source),'-i',str(clicks),
                    '-filter_complex','[0:a]volume=0.78[a];[a][1:a]amix=inputs=2:duration=shortest:normalize=0[out]',
                    '-map','[out]','-t',str(duration),'-c:a','libmp3lame','-b:a','160k',str(output)],cancel)
            progress(1)
        return self._queue('beat-preview',{'analysis_id':analysis_id,'plan':plan},worker,suffix='mp3')

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
