"""Real MCP handshake and audio calls using the exact portable plugin launch command."""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from scipy.io import wavfile
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from fusionify_audio.engine import SR
from test_engine import click_track


def payload(result):
    assert not result.isError,result
    return result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))


async def main():
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'mcp.json').read_text())['mcpServers']['fusionify-audio']
    with tempfile.TemporaryDirectory(prefix='fai-plugin-smoke-') as tmp:
        media=Path(tmp);wavfile.write(media/'test.wav',SR,click_track(128,8))
        env=dict(os.environ,FAI_MEDIA_ROOT=str(media),FAI_STATE_ROOT=str(media/'state'))
        # Resolve only the configured environment placeholders, as a client would.
        env.update({key:value.replace('${FAI_MEDIA_ROOT}',str(media)) for key,value in config.get('env',{}).items()})
        params=StdioServerParameters(command=config['command'],args=config['args'],env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools();assert len(tools.tools)==36
                workspace=payload(await session.call_tool('get_workspace'))
                assert workspace['version']=='0.6.1',workspace
                analysis=payload(await session.call_tool('analyze_audio',{'audio_path':'test.wav'}))
                assert analysis['duration_s']==8,analysis
                direction=payload(await session.call_tool('create_music_direction',{'analysis_id':analysis['analysis_id'],'section_count':2}))
                assert direction['accent_count']>0 and len(direction['sections'])==2
                print('PASS: portable uvx launcher, real MCP initialize/discovery, 36 tools, source audio analysis and music direction.')


if __name__=='__main__':asyncio.run(main())
