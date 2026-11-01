"""Persistent voice/transcript operations for the single-owner service."""
import json
import time
import uuid
from . import speech, transcript, voice


class VoiceTools:
    def analyze_voice(self,analysis_id: str,declared_source_type: str='mixed_audio') -> dict:
        _,y=self._verified_audio(analysis_id)
        report=voice.review(y,declared_source_type)
        voice_id=uuid.uuid4().hex
        row={'voice_id':voice_id,'analysis_id':analysis_id,**report}
        self.store.put('voice',voice_id,row)
        return {'voice_id':voice_id,'analysis_id':analysis_id,**report['summary'],
                'next':'Use get_voice_timeline for paginated pitch/activity/quiet ranges. Review against original audio.'}

    def voice_timeline(self,voice_id: str,offset: int=0,limit: int=100) -> dict:
        if type(offset)!=int or offset<0 or type(limit)!=int or not 1<=limit<=500:
            raise ValueError('Use nonnegative integer offset and limit 1 to 500.')
        row=self.store.get('voice',voice_id);end=offset+limit
        arrays={k:row[k][offset:end] for k in ('contour','activity_ranges','quiet_ranges')}
        return {'voice_id':voice_id,'analysis_id':row['analysis_id'],'summary':row['summary'],**arrays,
                'totals':{k:len(row[k]) for k in arrays},
                'next_offset':end if end<max(len(row[k]) for k in arrays) else None}

    def _save_transcript(self,analysis_id,segments,language,origin,review=None):
        report=self.record(analysis_id)['report']
        rows=transcript.validate_segments(segments,report['duration_s'])
        language=transcript.language_code(language);tid=uuid.uuid4().hex
        row={'transcript_id':tid,'analysis_id':analysis_id,'source_sha256':report['source']['sha256'],
             'duration_s':report['duration_s'],'language':language,'origin':origin,
             'audio_processed':origin in ('local_faster_whisper','local_signal_gate'),'created_at':time.time(),
             'time_reference':'seconds from source start','segments':rows,
             'limitations':[{'user_supplied':'Imported text is not acoustically verified.',
                             'local_signal_gate':'Exact digital silence: no ASR inference was run. Ordinary noise/quiet speech is not filtered by this gate.',
                             'local_faster_whisper':'ASR words and timestamps are estimates; inspect original audio.'}[origin]]}
        if review is not None:row['review']=review
        self.store.put('transcript',tid,row)
        return row

    def import_transcript(self,analysis_id: str,segments: list[dict],language: str|None=None) -> dict:
        self.record(analysis_id)
        row=self._save_transcript(analysis_id,segments,language,'user_supplied')
        return {k:v for k,v in row.items() if k!='segments'} | {'segment_count':len(row['segments'])}

    def transcribe_audio(self,analysis_id: str,language: str|None=None) -> dict:
        transcript.language_code(language);self.record(analysis_id)
        if not speech.availability()['ready_to_attempt']:
            raise ValueError('Local ASR is unavailable. Install the speech extra and configure FAI_WHISPER_MODEL_DIR, or import a timed transcript.')
        def worker(output,cancel,progress):
            _,y=self._verified_audio(analysis_id);progress(.1)
            result=speech.transcribe(y,language,output,cancel)
            if cancel.is_set():raise ValueError('Transcription cancelled.')
            from .transcript import review_hypothesis
            origin='local_signal_gate' if result.get('processing_method')=='digital_silence_gate' else 'local_faster_whisper'
            rows=transcript.validate_segments(result['segments'],self.record(analysis_id)['report']['duration_s'])
            review=review_hypothesis(rows,y,origin)
            row=self._save_transcript(analysis_id,rows,result['language'],origin,review)
            output.write_text(json.dumps(row,ensure_ascii=False,allow_nan=False),encoding='utf-8')
            return {'transcript_id':row['transcript_id'],'segment_count':len(row['segments']),
                    'origin':row['origin'],'language':row['language'],'review':review}
        return self._queue('local-transcription',{'analysis_id':analysis_id,'language':language},worker,suffix='json')

    def get_transcript(self,transcript_id: str,offset: int=0,limit: int=50,include_words: bool=False) -> dict:
        return transcript.page(self.store.get('transcript',transcript_id),offset,limit,include_words)

    def check_spoken_text(self,transcript_id: str,expected_text: str,max_edits: int=50) -> dict:
        return transcript.check(self.store.get('transcript',transcript_id),expected_text,max_edits)

    def export_transcript(self,transcript_id: str,format: str='srt',project_id: str|None=None) -> dict:
        if format not in ('srt','vtt','json'):raise ValueError('Transcript export must be srt, vtt or json.')
        row=self.store.get('transcript',transcript_id);start=0.;end=row['duration_s'];project=None
        if project_id:
            project=self.project(project_id)
            report=self.record(project['analysis_id'])['report']
            if report['source']['sha256']!=row['source_sha256']:raise ValueError('Transcript and project must use the same source audio.')
            start=project['timeline']['music_in_s'];end=start+project['timeline']['duration_s']
        if format=='json':
            if project_id:raise ValueError('JSON retains source-relative transcript. Use SRT/VTT for a project-relative export.')
            content=json.dumps(row,ensure_ascii=False,indent=2,allow_nan=False);details={'segment_count':len(row['segments'])}
        else:content,details=transcript.subtitle(row,format,start,end)
        aid=uuid.uuid4().hex;path=self.state_root/f'{aid}.{format}';path.write_text(content,encoding='utf-8')
        self.store.put('artifact',aid,{'path':str(path),'format':format})
        result={'artifact_id':aid,'format':format,'transcript_id':transcript_id,
                'time_reference':'seconds from project start' if project else 'seconds from source start',
                'source_in_s':start,**details}
        if project:result.update(project_id=project_id,revision=project['revision'])
        if self.artifact_url:result['download_url']=self.artifact_url(aid,format)
        else:result['output_path']=str(path)
        return result
