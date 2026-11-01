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
        root=Path(tmp);wavfile.write(root/'click.wav',SR,click_track(128,3))
        env=dict(os.environ,FAI_MEDIA_ROOT=str(root),FAI_STATE_ROOT=str(root/'state'))
        server=StdioServerParameters(command=sys.executable,args=['-m','fusionify_audio.cli','serve'],env=env)
        async with stdio_client(server) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                names={t.name for t in (await session.list_tools()).tools}
                assert names=={'analyze_audio','get_audio_timeline','create_edit_plan','render_visualizer','get_job_status'},names
                report=payload(await session.call_tool('analyze_audio',{'audio_path':'click.wav'}))
                assert report['duration_s']==3
                aid=report['analysis_id']
                timeline=payload(await session.call_tool('get_audio_timeline',{'analysis_id':aid}))
                assert timeline['beats']
                plan=payload(await session.call_tool('create_edit_plan',{'analysis_id':aid,'start_s':1,'duration_s':1}))
                assert plan['music_in_s']==1
                queued=payload(await session.call_tool('render_visualizer',{'analysis_id':aid,'start_s':1,'duration_s':1,'title':'MCP smoke test'}))
                for _ in range(120):
                    state=payload(await session.call_tool('get_job_status',{'job_id':queued['job_id']}))
                    if state['status'] in ('completed','failed'):break
                    await asyncio.sleep(.25)
                assert state['status']=='completed',state
                assert Path(state['output_path']).is_file()
                print('PASS: MCP stdio initialize, five tools, real analysis, offset plan, render and job polling.')


if __name__=='__main__':asyncio.run(main())
