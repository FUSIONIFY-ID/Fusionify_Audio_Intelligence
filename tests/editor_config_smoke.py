"""Exercise generated editor configs through MCP. This does not run native editor GUIs."""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

from fusionify_audio.engine import SR
from test_engine import click_track


CLIENT_PATHS={'cursor':'.cursor/mcp.json','kiro':'.kiro/settings/mcp.json','vscode':'.vscode/mcp.json'}


def payload(result):
    assert not result.isError,result
    return result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))


async def exercise(client,repo,root,artifact_dir):
    media=root/'selected media';media.mkdir(exist_ok=True)
    signal=click_track(128,12);wavfile.write(media/'test.wav',SR,signal)
    target=root/'project spaces'/CLIENT_PATHS[client]
    subprocess.run([sys.executable,str(repo/'scripts/configure_client.py'),'--client',client,
        '--launcher','portable','--media-root',str(media),'--state-root',str(root/f'state-{client}'),
        '--write',str(target)],check=True,stdout=subprocess.DEVNULL)
    document=json.loads(target.read_text())
    assert set(document)=={'servers' if client=='vscode' else 'mcpServers'},document
    entry=document['servers' if client=='vscode' else 'mcpServers']['fusionify-audio']
    params=StdioServerParameters(command=entry['command'],args=entry['args'],env={**os.environ,**entry['env']})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools();assert len(tools.tools)==37
            workspace=payload(await session.call_tool('get_workspace'))
            assert workspace['version']=='0.7.0',workspace
            analysis=payload(await session.call_tool('analyze_audio',{'audio_path':'test.wav'}))
            assert analysis['duration_s']==12,analysis
            direction=payload(await session.call_tool('create_music_direction',{
                'analysis_id':analysis['analysis_id'],'start_s':1,'duration_s':10,'section_count':2,
                'content_brief':'Synthetic editor connection check'}))
            assert direction['accent_count']>0 and len(direction['sections'])==2
            project=payload(await session.call_tool('create_video_project',{
                'analysis_id':analysis['analysis_id'],'options':{'visual_mode':'motion_graphics',
                'music_in_s':1,'duration_s':10,'resolution':480,'aspect':'1:1','motion_amount':.25,
                'story_blocks':[{'headline':'Connection check','visual':'globe'},
                                {'headline':'Full soundtrack range','visual':'spectrum'}]}}))
            fit=payload(await session.call_tool('review_content_fit',{'project_id':project['project_id']}))
            assert fit['status']=='no_structural_flags',fit
            sync=payload(await session.call_tool('review_music_sync',{'project_id':project['project_id']}))
            assert sync['boundary_count']==1 and sync['music_in_s']==1,sync
            queued=payload(await session.call_tool('render_video_project',{'project_id':project['project_id'],'preview':False}))
            deadline=asyncio.get_running_loop().time()+180
            while True:
                state=payload(await session.call_tool('get_job_status',{'job_id':queued['job_id']}))
                if state['status'] in ('completed','failed','cancelled','interrupted'):break
                if asyncio.get_running_loop().time()>deadline:raise AssertionError('Editor-config render exceeded 180 seconds.')
                await asyncio.sleep(.25)
            assert state['status']=='completed' and state['revision']==1 and state['preview'] is False,state
            video=Path(state['output_path']);assert video.is_file()
            meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
            stream=next(s for s in meta['streams'] if s['codec_type']=='video')
            assert (stream['width'],stream['height'])==(480,480),stream
            duration=float(meta['format']['duration']);assert abs(duration-10)<.08,duration
            assert any(s['codec_type']=='audio' for s in meta['streams']),meta
            raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-ac','1','-ar',str(SR),'-f','f32le','pipe:1'])
            actual=np.frombuffer(raw,dtype='<f4');expected=signal[SR:11*SR];n=min(len(actual),len(expected))
            assert n>=int(9.95*SR),n
            correlation=float(np.corrcoef(actual[:n],expected[:n])[0,1]);assert correlation>.98,correlation
            saved=payload(await session.call_tool('get_video_project',{'project_id':project['project_id']}))
            assert saved['revision']==1 and saved['duration_s']==10,saved
            if artifact_dir:
                destination=artifact_dir/f'{client}-synthetic-full.mp4'
                if destination.exists():raise ValueError('Choose a fresh artifact directory; existing videos are not overwritten.')
                shutil.copyfile(video,destination)
            return {'client_format':client,'engine_version':workspace['version'],'tools':len(tools.tools),
                    'source_is_synthetic':True,'source_duration_s':12,'music_in_s':1,'project_duration_s':10,
                    'render_duration_s':duration,'audio_correlation':round(correlation,6),
                    'native_editor_gui_tested':False,'result':'passed'}


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',choices=[*CLIENT_PATHS,'all'],default='all')
    parser.add_argument('--artifact-dir',type=Path,help='Optional directory for synthetic QA videos.')
    args=parser.parse_args()
    if args.artifact_dir:args.artifact_dir.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[1];results=[]
    with tempfile.TemporaryDirectory(prefix='fai-editor-config-') as tmp:
        for client in CLIENT_PATHS if args.client=='all' else [args.client]:
            print('Checking generated '+client+' configuration...',file=sys.stderr,flush=True)
            results.append(await exercise(client,repo,Path(tmp),args.artifact_dir))
    print(json.dumps(results,indent=2,allow_nan=False))


if __name__=='__main__':asyncio.run(main())
