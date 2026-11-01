"""Real MCP stdio initialize, discovery, calls, and a short render job."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from scipy.io import wavfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from test_engine import click_track
from fusionify_audio.engine import SR


def payload(result):
    if result.isError:raise AssertionError(result)
    value=result.structuredContent
    if value is not None:return value
    return json.loads(next(c.text for c in result.content if c.type=='text'))


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);wavfile.write(root/'click.wav',SR,click_track(128,12))
        env=dict(os.environ,FAI_MEDIA_ROOT=str(root),FAI_STATE_ROOT=str(root/'state'))
        server=StdioServerParameters(command=sys.executable,args=['-m','fusionify_audio.cli','serve'],env=env)
        async with stdio_client(server) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                names={t.name for t in (await session.list_tools()).tools}
                assert {'analyze_audio','get_audio_timeline','create_edit_plan','render_visualizer','get_job_status',
                        'create_video_project','revise_video_project','render_video_project','export_video_timeline',
                        'cancel_render_job','correct_beat_markers','import_media_url',
                        'get_rhythm_review','apply_tempo_map','estimate_tap_tempo',
                        'create_music_direction','review_content_fit'}.issubset(names),names
                report=payload(await session.call_tool('analyze_audio',{'audio_path':'click.wav'}))
                assert report['duration_s']==12
                aid=report['analysis_id']
                direction=payload(await session.call_tool('create_music_direction',{'analysis_id':aid,'content_brief':'Short product introduction'}))
                assert direction['sections'] and direction['accent_count']>0
                assert 'accents' not in direction
                anchored=payload(await session.call_tool('create_music_direction',{'analysis_id':aid,'start_s':1,'duration_s':10,
                    'section_count':3,'section_anchors':[{'section_index':1,'source_time_s':4.5}]}))
                assert anchored['sections'][1]['source_start_s']==4.5
                native=payload(await session.call_tool('create_video_project',{'analysis_id':aid,'options':{
                    'visual_mode':'motion_graphics','pacing_mode':'musical','music_in_s':1,'duration_s':10,
                    'section_anchors':[{'section_index':1,'source_time_s':4.5},{'section_index':2,'source_time_s':8}],
                    'story_blocks':[{'headline':x,'visual':'globe'} for x in ['Open','Product','Close']]}}))
                fit=payload(await session.call_tool('review_content_fit',{'project_id':native['project_id']}))
                assert fit['status']=='no_structural_flags'
                saved=payload(await session.call_tool('get_project_timeline',{'project_id':native['project_id']}))
                assert saved['music_sections'][2]['source_start_s']==8
                assert (await session.call_tool('render_video_project',{'project_id':native['project_id'],'preview_start_s':7})).isError
                excerpt=payload(await session.call_tool('render_video_project',{'project_id':native['project_id'],'preview':True,
                    'preview_start_s':7.25,'preview_duration_s':1}))
                assert excerpt['preview_start_s']==7.25 and excerpt['revision']==1
                for _ in range(120):
                    state=payload(await session.call_tool('get_job_status',{'job_id':excerpt['job_id']}))
                    if state['status'] in ('completed','failed'):break
                    await asyncio.sleep(.1)
                assert state['status']=='completed' and state['preview_duration_s']==1,state
                timeline=payload(await session.call_tool('get_audio_timeline',{'analysis_id':aid}))
                assert timeline['beats']
                review=payload(await session.call_tool('get_rhythm_review',{'analysis_id':aid}))
                assert len(review['waveform'])==1200
                taps=payload(await session.call_tool('estimate_tap_tempo',{'tap_times_s':[.4,.9,1.4,1.9]}))
                assert taps['tempo_bpm_estimate']==120
                assert (await session.call_tool('estimate_tap_tempo',{'tap_times_s':[0,.5,True,1.5]})).isError
                assert (await session.call_tool('render_beat_preview',{'analysis_id':aid,'click_volume':True})).isError
                assert (await session.call_tool('correct_beat_markers',{'analysis_id':aid,'beat_times_s':[True]})).isError
                mapped=payload(await session.call_tool('apply_tempo_map',{'analysis_id':aid,'regions':[
                    {'start_s':0,'end_s':3,'bpm':120,'first_beat_s':.4}],'snap_tolerance_s':.03}))
                assert mapped['parent_analysis_id']==aid and mapped['analysis_id']!=aid
                plan=payload(await session.call_tool('create_edit_plan',{'analysis_id':aid,'start_s':1,'duration_s':1}))
                assert plan['music_in_s']==1
                queued=payload(await session.call_tool('render_visualizer',{'analysis_id':aid,'start_s':1,'duration_s':1,'title':'MCP smoke test'}))
                for _ in range(120):
                    state=payload(await session.call_tool('get_job_status',{'job_id':queued['job_id']}))
                    if state['status'] in ('completed','failed'):break
                    await asyncio.sleep(.25)
                assert state['status']=='completed',state
                assert Path(state['output_path']).is_file()
                print(f'PASS: MCP stdio initialize, {len(names)} tools, real analysis, offset plan, render and job polling.')


if __name__=='__main__':asyncio.run(main())
