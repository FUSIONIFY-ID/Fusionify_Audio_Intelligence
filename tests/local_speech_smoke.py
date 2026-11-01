"""Opt-in real local-model QA. No model download and no external audio processing."""
import argparse
import asyncio
import os
import sys
import hashlib
import json
import platform
import re
import subprocess
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from fusionify_audio.engine import SR
from fusionify_audio.service import Service
from fusionify_audio.speech import availability,model_directory

SCRIPT='Hello world. This is a voice timing test. Please check the words carefully.'


def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def wait(service,job):
    started=time.monotonic()
    while time.monotonic()-started<190:
        state=service.status(job['job_id'])
        if state['status'] in ('completed','failed','cancelled'):break
        time.sleep(.1)
    assert state['status']=='completed',state
    return state,round(time.monotonic()-started,3)



async def exercise_stdio(root):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    def payload(result):
        assert not result.isError,result
        return result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))
    env=dict(os.environ,FAI_MEDIA_ROOT=str(root),FAI_STATE_ROOT=str(root/'mcp-state'))
    server=StdioServerParameters(command=sys.executable,args=['-m','fusionify_audio.cli','serve'],env=env)
    async with stdio_client(server) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            workspace=payload(await session.call_tool('get_workspace'))
            assert workspace['speech_review']['ready_to_attempt']
            a=payload(await session.call_tool('analyze_audio',{'audio_path':'clean.wav'}))
            job=payload(await session.call_tool('transcribe_audio',{'analysis_id':a['analysis_id'],'language':'en'}))
            started=time.monotonic()
            while time.monotonic()-started<190:
                state=payload(await session.call_tool('get_job_status',{'job_id':job['job_id']}))
                if state['status'] in ('completed','failed','cancelled'):break
                await asyncio.sleep(.1)
            assert state['status']=='completed',state
            tid=state['result']['transcript_id']
            saved=payload(await session.call_tool('get_transcript',{'transcript_id':tid,'include_words':True}))
            assert saved['origin']=='local_faster_whisper' and saved['review']['inference_performed']
            comparison=payload(await session.call_tool('check_spoken_text',{'transcript_id':tid,'expected_text':SCRIPT}))
            exported=payload(await session.call_tool('export_transcript',{'transcript_id':tid,'format':'srt'}))
            assert Path(exported['output_path']).read_text().count(' --> ')==exported['cue_count']>0
            return {'status':'passed','origin':saved['origin'],'edit_count':comparison['edit_count'],
                    'flagged_word_count':saved['review']['flagged_word_count'],'subtitle_cue_count':exported['cue_count']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Optional JSON report path; no source audio or model files are exported.')
    args=parser.parse_args()
    if not availability()['ready_to_attempt']:
        raise SystemExit('Supply a complete FAI_WHISPER_MODEL_DIR and install the speech extra. This script never downloads a model.')
    model=model_directory()
    report={'fixture':'FFmpeg libflite slt synthetic English narration',
            'expected_script':SCRIPT,'model_sha256':checksum(model/'model.bin'),
            'runtime_versions':{name:version(name) for name in ['faster-whisper','ctranslate2','av','numpy']},
            'python':platform.python_version(),'cases':[],
            'limitations':['Synthetic English only; not an Indonesian, singing or real remix benchmark.',
                           'Time bounds are checked; estimated word alignment is not verified against phoneme ground truth.',
                           'WER measures transcript differences on these fixtures, not pronunciation or general model accuracy.']}
    with tempfile.TemporaryDirectory(prefix='fai-local-speech-qa-') as tmp:
        root=Path(tmp)
        try:
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                f'flite=text={SCRIPT}:voice=slt','-ar',str(SR),'-ac','1',str(root/'clean.wav')],
                capture_output=True,check=True,timeout=30)
        except subprocess.CalledProcessError:
            raise SystemExit('This fixture requires FFmpeg built with the libflite source filter.') from None
        rate,pcm=wavfile.read(root/'clean.wav');assert rate==SR and pcm.dtype==np.int16
        y=pcm.astype('float32')/32768
        t=np.arange(len(y))/rate;p=t%.5
        bed=.1*np.sin(2*np.pi*130.81*t)+.07*np.sin(2*np.pi*196*t)+.4*np.exp(-p*35)*np.sin(2*np.pi*(50*p+3*(1-np.exp(-p*30))))
        bed*=np.sqrt(np.mean(y*y))/np.sqrt(np.mean(bed*bed))
        for name,samples in [('silence',np.zeros(rate*5)),('light_bed',y+bed*.125),('equal_bed',y+bed)]:
            wavfile.write(root/f'{name}.wav',rate,samples.astype('float32'))
        service=Service(root,root/'state')
        try:
            for name in ['clean','silence','light_bed','equal_bed']:
                analysis=service.analyze(name+'.wav');aid=analysis['analysis_id']
                state,runtime=wait(service,service.transcribe_audio(aid,'en'))
                tid=state['result']['transcript_id'];record=service.get_transcript(tid,include_words=True)
                expected_origin='local_signal_gate' if name=='silence' else 'local_faster_whisper'
                assert record['origin']==expected_origin and record['audio_processed']
                item={'case':name,'duration_s':record['duration_s'],'runtime_s':runtime,'origin':record['origin'],
                      'text':' '.join(s['text'].strip() for s in record['segments']),
                      'word_count':sum(len(s.get('words',[])) for s in record['segments']),
                      'review':record['review']}
                if name=='silence':
                    assert not record['segments'] and not record['review']['inference_performed']
                else:
                    assert record['segments'],'Known synthetic narration produced no transcript.'
                    comparison=service.check_spoken_text(tid,SCRIPT)
                    item['comparison']={k:comparison[k] for k in ['edit_count','word_error_rate','edits']}
                    project=service.create_project(aid,{'music_in_s':1,'duration_s':2})
                    export=service.export_transcript(tid,'vtt',project['project_id'])
                    text=Path(export['output_path']).read_text()
                    assert text.startswith('WEBVTT') and export['cue_count']>0
                    def seconds(stamp):
                        h,m,s=stamp.split(':');return int(h)*3600+int(m)*60+float(s)
                    stamps=re.findall(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})',text)
                    assert len(stamps)==export['cue_count']
                    assert all(0<=seconds(a)<seconds(b)<=2.001 for a,b in stamps)
                    item['project_subtitles']={k:export[k] for k in ['cue_count','source_in_s',
                        'partial_segments_review_required','words_crossing_trim_omitted']}
                report['cases'].append(item)
                print(json.dumps({'case':name,'runtime_s':runtime,'origin':record['origin'],
                    'word_count':item['word_count'],'edit_count':item.get('comparison',{}).get('edit_count')}),flush=True)
        finally:service.close()
        report['mcp_stdio']=asyncio.run(exercise_stdio(root))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
