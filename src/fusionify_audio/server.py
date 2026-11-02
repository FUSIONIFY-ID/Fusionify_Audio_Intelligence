"""MCP v1 stdio / HTTP tool adapter for the creator workspace."""
import asyncio
from pydantic import StrictInt
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from .project import ProjectOptions
from .rhythm import Number, TempoRegion
from .direction import SectionAnchor
from .service import Service
from .transcript import Segment


def project_summary(project: dict) -> dict:
    return {k:v for k,v in project.items() if k!='timeline'} | {
        'duration_s':project['timeline']['duration_s'], 'scene_count':len(project['timeline']['scenes']),
        'warnings':project['timeline']['warnings']}


def build_server(service: Service, http: bool=False, allowed_hosts: list[str]|None=None,
                 allowed_origins: list[str]|None=None) -> FastMCP:
    mcp=FastMCP('Fusionify Audio Intelligence',instructions=(
        'Analyze actual source files before planning edits. Beat, tempo and energy markers are estimates. '
        'Get workspace upload instructions before assuming chat attachments are accessible. '
        'Persist and revise video projects; preserve full source duration unless a shorter range is requested. '
        'Preview is explicitly limited to eight seconds. Final render uses the project duration. '
        'Do not claim semantic listening from DSP, confirmed drops or universal music support. '
        'Keep transcript origin and estimated word timing explicit; text agreement is not pronunciation accuracy. '
        'Poll jobs; only present download_url when returned, otherwise output_path is local.'),
        stateless_http=http,json_response=http,max_request_body_size=1024*1024,
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts or ['127.0.0.1:*','localhost:*'],
                                                      allowed_origins=allowed_origins or []))
    read=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
    write=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)

    @mcp.tool(annotations=read)
    def get_workspace() -> dict:
        """Get supported styles/formats, upload URL if hosted, and workspace limits. No credentials returned."""
        return service.workspace()

    @mcp.tool(annotations=read)
    def list_media_assets(limit: int=50) -> dict:
        """List up to 100 registered audio/image/video assets and their IDs."""
        return {'assets':service.assets(limit)}

    @mcp.tool(annotations=write)
    async def register_media_asset(path: str, label: str|None=None) -> dict:
        """Register an existing file inside FAI_MEDIA_ROOT. HTTP uploads register assets automatically."""
        return await asyncio.to_thread(service.register_asset,path,label)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=True))
    async def import_media_url(url: str) -> dict:
        """Import a direct HTTPS media file only from operator-allowlisted public hosts, up to 64 MiB.

        Streaming service pages, authenticated subscriptions and arbitrary hosts are unsupported.
        """
        return await asyncio.to_thread(service.import_url,url)

    @mcp.tool(annotations=write)
    async def analyze_audio(audio_path: str) -> dict:
        """Analyze actual audio using a registered audio/video asset ID or local path inside FAI_MEDIA_ROOT."""
        return await asyncio.to_thread(service.analyze,audio_path)

    @mcp.tool(annotations=read)
    def get_audio_profile(analysis_id: str) -> dict:
        """Get duration, estimated global/local tempos, measured spectral/level features and limitations."""
        return service.profile(analysis_id)

    @mcp.tool(annotations=write)
    async def analyze_voice(analysis_id: str, declared_source_type: str='mixed_audio') -> dict:
        """Measure periodic pitch (60–500 Hz), signal activity, pauses and headroom offline.

        Declare speech only for speech-dominant audio. Mixed music may track instruments.
        Does not separate vocals, infer emotion/identity or score pronunciation/intonation correctness.
        """
        return await asyncio.to_thread(service.analyze_voice,analysis_id,declared_source_type)

    @mcp.tool(annotations=read)
    def get_voice_timeline(voice_id: str, offset: StrictInt=0, limit: StrictInt=100) -> dict:
        """Page source-relative pitch contour, activity and quiet ranges; at most 500 items per array."""
        return service.voice_timeline(voice_id,offset,limit)

    @mcp.tool(annotations=write)
    def transcribe_audio(analysis_id: str, language: str|None=None) -> dict:
        """Queue optional local-only faster-whisper ASR. Poll get_job_status for result.transcript_id.

        Requires installed speech extra and operator FAI_WHISPER_MODEL_DIR. No automatic download
        or external audio upload. Transcript and word times are estimates, especially over music.
        Exact all-zero PCM skips inference with local_signal_gate origin. Inspect result.review flags.
        """
        return service.transcribe_audio(analysis_id,language)

    @mcp.tool(annotations=write)
    def import_transcript(analysis_id: str, segments: list[Segment], language: str|None=None) -> dict:
        """Save up to 500 ordered timed segments supplied by the user. This does not verify audio.

        Source-relative seconds; optional words must match text and fit within each segment.
        """
        return service.import_transcript(analysis_id,[s.model_dump(exclude_none=True) for s in segments],language)

    @mcp.tool(annotations=read)
    def get_transcript(transcript_id: str, offset: StrictInt=0, limit: StrictInt=50, include_words: bool=False) -> dict:
        """Read a paginated transcript with origin, listening-review flags and limitations.

        Enable words for estimated word times. Low model scores are not calibrated accuracy;
        no flags is not verified speech. Signal-gated digital silence explicitly records no inference.
        """
        return service.get_transcript(transcript_id,offset,limit,include_words)

    @mcp.tool(annotations=read)
    async def check_spoken_text(transcript_id: str, expected_text: str, max_edits: StrictInt=50) -> dict:
        """Compare a supplied script to transcript tokens: omissions, additions, substitutions and spans.

        Imported text is text-only; ASR can mishear. Agreement does not prove pronunciation or
        intonation. Number spellings/homophones are not silently equated. No automatic pass verdict.
        """
        return await asyncio.to_thread(service.check_spoken_text,transcript_id,expected_text,max_edits)

    @mcp.tool(annotations=write)
    def export_transcript(transcript_id: str, format: str='srt', project_id: str|None=None) -> dict:
        """Export SRT/VTT or source-relative JSON. Optional project clips/shifts matching-source subtitles.

        Partial segments without complete in-range word timings are omitted and reported.
        Project-relative JSON is unsupported. Does not burn subtitles into video.
        """
        return service.export_transcript(transcript_id,format,project_id)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=True))
    async def describe_music(analysis_id: str, question: str, allow_external_processing: bool=False) -> dict:
        """Optional Gemini interpretation of actual audio: mood, texture and editing suggestions.

        Requires server-side GEMINI_API_KEY and FAI_GEMINI_MODEL, and explicit user agreement
        to send music to Google. May incur provider charges. Never silently invoke this for DSP analysis.
        Live provider integration is experimental; timing must come from measured DSP or user corrections.
        """
        return await asyncio.to_thread(service.describe_audio,analysis_id,question,allow_external_processing)

    @mcp.tool(annotations=write)
    def render_beat_preview(analysis_id: str, start_s: float=0, duration_s: float|None=None, click_volume: Number=1) -> dict:
        """Queue audible timing review, full duration by default. click_volume=0 keeps original music level.

        Click volume accepts 0 to 2; positive volume adds markers and lowers music to 78 percent.
        Save edited markers as a new analysis before requesting a matching click preview.
        """
        return service.beat_preview(analysis_id,start_s,duration_s,click_volume)

    @mcp.tool(annotations=read)
    async def get_rhythm_review(analysis_id: str) -> dict:
        """Get 1200 min/max waveform bins, complete beat markers and provenance for timing review.

        Source is verified against its analysis hash. Times are seconds from the exact source start.
        """
        return await asyncio.to_thread(service.rhythm_review,analysis_id)

    @mcp.tool(annotations=read)
    def estimate_tap_tempo(tap_times_s: list[Number]) -> dict:
        """Estimate 30-300 BPM from 4-128 ordered source-relative taps; reject inconsistent input.

        Does not save anything or prove musical accuracy. Use the returned BPM in an explicit tempo map.
        """
        return service.tap_tempo(tap_times_s)

    @mcp.tool(annotations=write)
    async def apply_tempo_map(analysis_id: str, regions: list[TempoRegion], snap_tolerance_s: Number=0) -> dict:
        """Create a new timing analysis from 1-32 user-directed tempo regions, retaining the original.

        Each region has source-relative start_s, end_s, first_beat_s and bpm (30-300).
        Regions must be ordered and non-overlapping; end is exclusive, gaps contain no beats.
        Optional snap_tolerance_s (0-0.1) aligns only nearby measured onsets. Unsnapped points are
        labeled user tempo grid. This is not automatic variable-tempo or downbeat detection.
        Existing projects keep old timing; create a new project with the returned analysis_id.
        """
        return await asyncio.to_thread(service.apply_tempo_map,analysis_id,[r.model_dump() for r in regions],snap_tolerance_s)

    @mcp.tool(annotations=write)
    def export_audio_analysis(analysis_id: str, format: str='json') -> dict:
        """Export measured analysis JSON or a waveform SVG with estimated beat markers."""
        return service.export_analysis(analysis_id,format)

    @mcp.tool(annotations=read)
    def list_video_projects(limit: int=50) -> dict:
        """Find saved project IDs/revisions after reconnecting to the same workspace."""
        return {'projects':service.list_projects(limit)}

    @mcp.tool(annotations=read)
    def list_render_jobs(limit: int=50) -> dict:
        """Find persistent render jobs and refresh expiring artifact links."""
        return {'jobs':service.list_jobs(limit)}

    @mcp.tool(annotations=read)
    def compare_audio(analysis_id_a: str, analysis_id_b: str) -> dict:
        """Compare measured duration, pulse estimate and signal features of two actual analyses."""
        a=service.profile(analysis_id_a);b=service.profile(analysis_id_b)
        return {'a':a,'b':b,'note':'Measured comparison; mood, quality and genre are not inferred.'}

    @mcp.tool(annotations=read)
    def get_audio_timeline(analysis_id: str, start_s: float=0, end_s: float|None=None, limit: int=100) -> dict:
        """Read source-relative beat/energy candidates for a bounded range. Narrow the range if truncated."""
        return service.timeline(analysis_id,start_s,end_s,limit)

    @mcp.tool(annotations=write)
    def correct_beat_markers(analysis_id: str, beat_times_s: list[Number]) -> dict:
        """Create a new analysis with user-provided source-relative markers; retain the original analysis."""
        return service.correct_beats(analysis_id,beat_times_s)

    @mcp.tool(annotations=read)
    def create_edit_plan(analysis_id: str, start_s: float=0, duration_s: float|None=None, intensity: str='medium') -> dict:
        """Create timing suggestions without saving a project; omit duration for all remaining music."""
        return service.plan(analysis_id,start_s,duration_s,intensity)

    @mcp.tool(annotations=read)
    def create_music_direction(analysis_id: str, start_s: float=0, duration_s: float|None=None,
                               intensity: str='medium', section_count: StrictInt=5, content_brief: str='',
                               section_anchors: list[SectionAnchor]|None=None) -> dict:
        """Propose music-to-content pacing from measured audio and a user content brief.

        Separates 1-8 readable editorial sections from small beat-driven motion accents.
        Returns source/video times, energy levels and boundary evidence. Opening/feature/closing
        are creative roles, not detected chorus/drop/downbeats. Does not save or render anything.
        Use pacing_mode=musical on the next project, and story_blocks for native motion graphics.
        Optional section_anchors lock a zero-based section_index at absolute source_time_s.
        Zero is the implicit first section, so index 2 means the third. Anchors accept indices 1-7.
        Section zero starts at start_s. User anchors are not detected musical events.
        """
        return service.music_direction(analysis_id,start_s,duration_s,intensity,section_count,content_brief,
                                       [a.model_dump() for a in section_anchors] if section_anchors is not None else None)

    @mcp.tool(annotations=write)
    def create_video_project(analysis_id: str, options: ProjectOptions|None=None) -> dict:
        """Save an edit project: style, intensity, title/caption, music range, image/video IDs and output size.

        Default no assets means a waveform visualizer; images/videos create a montage.
        Choose visual_mode=motion_graphics for native globe/spectrum/orbit/audio-chart story blocks,
        pacing_mode=musical for readable scenes plus beat accents, and text_overlay=false for already
        composed footage. video_playback=source_sync follows soundtrack source time without slowing
        an existing music-synchronized clip when images are interleaved. Market visuals are illustrative.
        """
        return project_summary(service.create_project(analysis_id,options.model_dump() if options else {}))

    @mcp.tool(annotations=read)
    def get_video_project(project_id: str) -> dict:
        """Get saved project options and revision number before editing or rendering."""
        return project_summary(service.project(project_id))

    @mcp.tool(annotations=read)
    def review_content_fit(project_id: str) -> dict:
        """Check saved music/video structure for rapid cuts, possible duplicate text and footage-clock/loop risks.

        Checks are explicit structural heuristics, not a claim to see footage or hear perfect sync.
        Inspect the actual preview and brief. Use this before delivering a new edit, especially composed clips.
        """
        return service.content_fit(project_id)

    @mcp.tool(annotations=read)
    def review_music_sync(project_id: str, tolerance_ms: Number=80, offset: StrictInt=0, limit: StrictInt=100) -> dict:
        """Review saved scene cuts against pulse/energy candidates at full-render frame times.

        Read-only, paginated evidence with source/video clocks, signed offsets in milliseconds,
        marker provenance and up to three project-relative listening preview ranges.
        Positive offset means the cut follows the candidate. Tolerance is 0-250 ms, not accuracy.
        Intentional editorial cuts may be far from candidates. No automatic corrections or drop detection.
        Continuous waveform visualizers have no scene boundaries. Check revision before rendering
        a suggested range; pass only project_id, preview, preview_start_s and preview_duration_s
        to render_video_project. Inspect the actual audio/video before proposing revisions.
        """
        return service.music_sync(project_id,tolerance_ms,offset,limit)

    @mcp.tool(annotations=read)
    def get_project_timeline(project_id: str, offset: int=0, limit: int=100) -> dict:
        """Get a page of saved render scenes. Scene times are video-relative, with music_in_s supplied."""
        if not 0<=offset or not 1<=limit<=500:raise ValueError('Invalid page range.')
        project=service.project(project_id);timeline=project['timeline'];scenes=timeline['scenes']
        return {'project_id':project_id,'revision':project['revision'],'music_in_s':timeline['music_in_s'],
                'music_sections':timeline['music_direction']['sections'] if timeline.get('music_direction') else [],
                'section_anchors':project['options'].get('section_anchors',[]),
                'scenes':scenes[offset:offset+limit],'total':len(scenes),'next_offset':offset+limit if offset+limit<len(scenes) else None}

    @mcp.tool(annotations=write)
    def revise_video_project(project_id: str, expected_revision: int, changes: dict) -> dict:
        """Revise allowed ProjectOptions fields, retaining project identity. Stale revisions are rejected.

        Fields: title, caption, style, intensity, aspect, resolution, music_in_s, duration_s,
        asset_ids, audio_gain_db, motion_amount, fit_mode, scene_overrides.
        Also pacing_mode, visual_mode, text_overlay, video_playback, brand, accent_color,
        content_brief and story_blocks (headline/support/visual).
        section_anchors can lock later musical sections at explicit source-relative timestamps.
        Unknown fields, executable code and filter strings are rejected.
        """
        return project_summary(service.revise_project(project_id,expected_revision,changes))

    @mcp.tool(annotations=write)
    def render_video_project(project_id: str, preview: bool=False, preview_start_s: Number=0,
                             preview_duration_s: Number|None=None) -> dict:
        """Queue rendering. preview=true permits a targeted excerpt up to eight seconds at low resolution.

        Final renders preserve project duration. Registered footage audio is muted; chosen music is used.
        preview_start_s uses the saved project's video clock, not absolute source time. Excerpts retain
        saved story identity and continuous motion/source clocks. No project revision is changed.
        Non-default preview range parameters are rejected when preview=false. Poll the returned job.
        """
        return service.render_project(project_id,preview,preview_start_s,preview_duration_s)

    @mcp.tool(annotations=write)
    def render_visualizer(analysis_id: str, title: str='Your sound. In motion.', start_s: float=0,
                          duration_s: float|None=None, intensity: str='medium') -> dict:
        """Queue a waveform video with original music, optionally trimmed. Defaults to full remaining duration."""
        return service.render(analysis_id,title,start_s,duration_s,intensity)

    @mcp.tool(annotations=read)
    def get_job_status(job_id: str) -> dict:
        """Get persistent job status/progress, failure, local output path or hosted expiring download URL."""
        return service.status(job_id)

    @mcp.tool(annotations=write)
    def cancel_render_job(job_id: str) -> dict:
        """Cancel an active or queued render. Completed artifacts are retained."""
        return service.cancel_job(job_id)

    @mcp.tool(annotations=write)
    def export_video_timeline(project_id: str, format: str='json') -> dict:
        """Export a saved project as JSON or scene markers as CSV, with local path or expiring download URL."""
        return service.export(project_id,format)

    return mcp
