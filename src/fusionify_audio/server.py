"""MCP v1 stdio adapter for Claude Desktop and Claude Code."""
import asyncio
from mcp.server.fastmcp import FastMCP
from .service import Service


def build_server(service: Service) -> FastMCP:
    mcp=FastMCP('Fusionify Audio Intelligence',instructions=(
        'Analyze actual source files before planning edits. Beat, tempo and energy markers are estimates. '
        'Do not claim semantic listening, confirmed drops or support for all music. '
        'This v0.1 server is local-only. Never claim an output_path is a public download URL.'))

    @mcp.tool()
    async def analyze_audio(audio_path: str) -> dict:
        """Analyze a local music file inside FAI_MEDIA_ROOT; return ID and compact timing summary."""
        return await asyncio.to_thread(service.analyze,audio_path)

    @mcp.tool()
    def get_audio_timeline(analysis_id: str, start_s: float=0, end_s: float|None=None, limit: int=100) -> dict:
        """Read estimated source-relative beats and energy in a bounded time range, up to 500 items per series."""
        return service.timeline(analysis_id,start_s,end_s,limit)

    @mcp.tool()
    def create_edit_plan(analysis_id: str, start_s: float=0, duration_s: float|None=None, intensity: str='medium') -> dict:
        """Create a music-relative cut/scale plan. Omit duration for the full remaining audio. Flash stays off."""
        return service.plan(analysis_id,start_s,duration_s,intensity)

    @mcp.tool()
    def render_visualizer(analysis_id: str, title: str='Your sound. In motion.', start_s: float=0,
                          duration_s: float|None=None, intensity: str='medium') -> dict:
        """Queue a vertical 480x854 waveform video with original soundtrack and beat-driven scale pulses.

        This renders a fixed visualizer, not arbitrary footage editing or a generative video model.
        Returns a job ID; use get_job_status later. One active render per local server.
        """
        return service.render(analysis_id,title,start_s,duration_s,intensity)

    @mcp.tool()
    def get_job_status(job_id: str) -> dict:
        """Get local render status. Completed jobs include a local output_path; failed jobs include an error."""
        return service.status(job_id)

    return mcp
