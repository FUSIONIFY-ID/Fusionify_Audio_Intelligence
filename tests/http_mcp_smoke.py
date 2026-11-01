"""Actual TCP HTTP MCP initialization and tool calls with bearer auth."""
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from scipy.io import wavfile
from fusionify_audio.engine import SR
from test_engine import click_track
from voice_smoke_helpers import exercise_voice


def result_data(result):
    assert not result.isError,result
    return result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,12))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}';token=secrets.token_urlsafe(48)
        env=dict(os.environ,FAI_MEDIA_ROOT=str(root),FAI_STATE_ROOT=str(root/'state'),FAI_API_TOKEN=token)
        with tempfile.TemporaryFile() as logs:
            process=subprocess.Popen([sys.executable,'-m','fusionify_audio.cli','serve-http','--port',str(port)],env=env,stdout=logs,stderr=logs)
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
                    for _ in range(100):
                        try:
                            if (await client.get(base+'/healthz')).status_code==200:break
                        except httpx.TransportError:pass
                        if process.poll() is not None:raise AssertionError('HTTP server exited before startup.')
                        await asyncio.sleep(.1)
                    else:raise AssertionError('HTTP startup timeout.')
                    assert (await client.post(base+'/mcp',json={})).status_code==401
                async with streamablehttp_client(base+'/mcp',headers={'Authorization':'Bearer '+token},
                    httpx_client_factory=lambda **kw:httpx.AsyncClient(trust_env=False,**kw)) as (read,write,_):
                    async with ClientSession(read,write) as session:
                        await session.initialize()
                        names={t.name for t in (await session.list_tools()).tools}
                        assert 'render_video_project' in names
                        result=await session.call_tool('analyze_audio',{'audio_path':'track.wav'})
                        assert not result.isError,result
                        report=result_data(result)
                        assert report['duration_s']==12,report
                        aid=report['analysis_id']
                        subtitle=await exercise_voice(session,aid,result_data)
                        async with httpx.AsyncClient(trust_env=False) as downloads:
                            response=await downloads.get(subtitle['download_url'])
                            assert response.status_code==200 and response.headers['content-type'].startswith('text/vtt')
                            assert '00:00:00.000 --> 00:00:01.000' in response.text
                        direction=result_data(await session.call_tool('create_music_direction',{'analysis_id':aid,'section_count':3,
                            'section_anchors':[{'section_index':1,'source_time_s':4.5}],'content_brief':'Short editorial test'}))
                        assert direction['sections'][1]['source_start_s']==4.5
                        project=result_data(await session.call_tool('create_video_project',{'analysis_id':aid,'options':{
                            'visual_mode':'motion_graphics','story_blocks':[{'headline':h} for h in ['Open','Middle','Close']],
                            'section_anchors':[{'section_index':1,'source_time_s':4.5}]}}))
                        excerpt=result_data(await session.call_tool('render_video_project',{'project_id':project['project_id'],
                            'preview':True,'preview_start_s':5,'preview_duration_s':1}))
                        for _ in range(120):
                            state=result_data(await session.call_tool('get_job_status',{'job_id':excerpt['job_id']}))
                            if state['status'] in ('completed','failed'):break
                            await asyncio.sleep(.1)
                        assert state['status']=='completed' and state['preview_start_s']==5 and state['download_url'].startswith(base+'/downloads/'),state
                        review=result_data(await session.call_tool('get_rhythm_review',{'analysis_id':aid}))
                        assert len(review['waveform'])==1200
                        mapped=result_data(await session.call_tool('apply_tempo_map',{'analysis_id':aid,'regions':[
                            {'start_s':0,'end_s':3,'bpm':120,'first_beat_s':.4}]}))
                        assert mapped['parent_analysis_id']==aid
                        assert result_data(await session.call_tool('estimate_tap_tempo',{'tap_times_s':[.4,.9,1.4,1.9]}))['tempo_bpm_estimate']==120
                        workspace=result_data(await session.call_tool('get_workspace'))
                        assert workspace['upload_url']==base+'/'
                print('PASS: TCP Streamable HTTP MCP auth, initialization, discovery and real audio analysis.')
            finally:
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':asyncio.run(main())
