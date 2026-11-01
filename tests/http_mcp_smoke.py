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


def result_data(result):
    assert not result.isError,result
    return result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);wavfile.write(root/'track.wav',SR,click_track(128,3))
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
                        assert report['duration_s']==3,report
                        workspace=result_data(await session.call_tool('get_workspace'))
                        assert workspace['upload_url']==base+'/'
                print('PASS: TCP Streamable HTTP MCP auth, initialization, discovery and real audio analysis.')
            finally:
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':asyncio.run(main())
