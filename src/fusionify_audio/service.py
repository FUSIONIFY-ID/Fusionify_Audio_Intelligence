"""Single-user local storage and bounded background rendering."""
from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .engine import analyze, media_file
from .render import edit_plan, visualizer


class Service:
    def __init__(self, media_root: Path, state_root: Path):
        self.media_root=media_root.expanduser().resolve(strict=True)
        self.state_root=state_root.expanduser().resolve()
        self.state_root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='fai-render')
        self.jobs={}
        self.lock=threading.Lock()

    def _record_path(self, analysis_id: str) -> Path:
        if not re.fullmatch(r'[a-f0-9]{32}',analysis_id):
            raise ValueError('Invalid analysis ID.')
        return self.state_root / f'{analysis_id}.json'

    def analyze(self, audio_path: str) -> dict:
        source=media_file(self.media_root,audio_path)
        report,_=analyze(source)
        analysis_id=uuid.uuid4().hex
        record={'source_path':str(source),'report':report}
        self._record_path(analysis_id).write_text(json.dumps(record,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        return {'analysis_id':analysis_id,'source':report['source'],'duration_s':report['duration_s'],
                'tempo_bpm_estimate':report['tempo_bpm_estimate'],'beat_count':len(report['beats']),
                'transitions':report['transitions'],'warnings':report['warnings'],
                'next':'Use get_audio_timeline for bounded timing data or create_edit_plan.'}

    def record(self, analysis_id: str) -> dict:
        return json.loads(self._record_path(analysis_id).read_text(encoding='utf-8'))

    def timeline(self, analysis_id: str, start_s: float=0, end_s: float|None=None, limit: int=100) -> dict:
        import math
        report=self.record(analysis_id)['report']
        end_s=report['duration_s'] if end_s is None else end_s
        if not all(math.isfinite(v) for v in (start_s,end_s)) or not 0<=start_s<end_s<=report['duration_s']+.001:
            raise ValueError('Select a finite range within source duration.')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500:
            raise ValueError('Limit must be an integer from 1 to 500.')
        beats=[b for b in report['beats'] if start_s<=b['time_s']<end_s]
        return {'analysis_id':analysis_id,'time_reference':report['time_reference'],
                'beats':beats[:limit], 'total_in_range':len(beats), 'truncated':len(beats)>limit,
                'energy':[e for e in report['energy'] if start_s<=e['time_s']<end_s][:limit],
                'energy_truncated':sum(start_s<=e['time_s']<end_s for e in report['energy'])>limit,
                'transitions':[e for e in report['transitions'] if start_s<=e['time_s']<end_s]}

    def plan(self, analysis_id: str, start_s: float=0, duration_s: float|None=None, intensity: str='medium') -> dict:
        return {'analysis_id':analysis_id,**edit_plan(self.record(analysis_id)['report'],start_s,duration_s,intensity)}

    def render(self, analysis_id: str, title: str='Your sound. In motion.', start_s: float=0,
               duration_s: float|None=None, intensity: str='medium') -> dict:
        if not 1<=len(title)<=80:
            raise ValueError('Title must contain 1 to 80 characters.')
        plan=self.plan(analysis_id,start_s,duration_s,intensity)
        with self.lock:
            if any(j['status'] in ('queued','running') for j in self.jobs.values()):
                raise ValueError('One render is already active. Check its status first.')
            if len(self.jobs)>=100:
                raise ValueError('Local session job limit reached; restart the service to clear job history.')
            job_id=uuid.uuid4().hex
            self.jobs[job_id]={'job_id':job_id,'status':'queued','analysis_id':analysis_id}
        def work():
            with self.lock:self.jobs[job_id]['status']='running'
            try:
                record=self.record(analysis_id)
                source=media_file(self.media_root,record['source_path'])
                report,y=analyze(source)
                if report['source']['sha256']!=record['report']['source']['sha256']:
                    raise ValueError('Source changed since analysis; analyze it again.')
                output=self.state_root/f'{job_id}.mp4'
                visualizer(source,y,plan,output,title)
                with self.lock:self.jobs[job_id].update(status='completed',output_path=str(output))
            except Exception as exc:
                with self.lock:self.jobs[job_id].update(status='failed',error=str(exc))
        self.pool.submit(work)
        return {'job_id':job_id,'status':'queued','next':'Call get_job_status; output is a local file, not a hosted download URL.'}

    def status(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.jobs:raise ValueError('Unknown job ID in this server session.')
            return dict(self.jobs[job_id])

    def close(self):
        self.pool.shutdown(wait=True)
