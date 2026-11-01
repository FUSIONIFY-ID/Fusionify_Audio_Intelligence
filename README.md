# Fusionify Audio Intelligence

**Your music. Your visual direction.**

Give Claude real audio timing, a revisable video project, and tools to turn your music and visuals into a finished edit. Built for JJ, remix, breakbeat, promos, cinematic montages, and waveform videos.

## What v0.2 does

| Capability | Implementation |
| --- | --- |
| Real audio analysis | Duration, global pulse estimate, local tempo windows, beat candidates, energy rises, RMS/peak and spectral measurements |
| Timing review | Full-length click preview, waveform SVG, JSON analysis, manual beat corrections retained as a new analysis |
| Media inputs | Local files, authenticated browser uploads, restricted direct HTTPS imports |
| Video projects | Persistent projects, revision checks, title/caption, music range, asset selection, motion strength, cover/contain, explicit scene overrides |
| Montage rendering | User photos and MP4/MOV clips, original soundtrack, fixed cut/zoom/pan/shake effects |
| Styles | JJ/remix, cinematic, product promo, minimal; low/medium/high intensity |
| Output | 9:16, 16:9, 1:1; short side 480/720/1080 pixels; explicit preview or full project render |
| Render management | Bounded queue, progress, cancellation, persistent results, interrupted-job recovery |
| Timeline exports | Project JSON and CSV scene markers |
| Claude integration | Stdio MCP, authenticated Streamable HTTP MCP, Claude Code plugin and three companion skills |
| Creator console | Token-gated upload, audio analysis, project settings, render preview and download |
| Optional music interpretation | Gemini adapter for mood/texture/visual suggestions; explicit external-processing agreement and operator credentials required |

The core engine uses DSP and runs without a paid model API. The optional Gemini adapter is separately enabled and has mocked contract tests; live provider behavior requires a real configured account and is not claimed by those tests.

Automatic beat markers are estimates. An energy rise is a transition candidate, not a confirmed musical drop. Local tempo windows aid inspection; the current beat grid still uses a global estimate and may miss tempo-changing passages. No claim of perfect alignment for every song.

## Quick start: local CLI

Install Python 3.11+, [uv](https://docs.astral.sh/uv/), FFmpeg and ffprobe. Then:

```bash
git clone https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence.git
cd Fusionify_Audio_Intelligence
uv sync --frozen
uv run fusionify-audio doctor
```

macOS/Linux:

```bash
export FAI_MEDIA_ROOT="/absolute/path/to/music-and-visuals"
uv run fusionify-audio analyze "track.mp3"
uv run fusionify-audio profile ANALYSIS_ID
uv run fusionify-audio create-project ANALYSIS_ID
uv run fusionify-audio render-project PROJECT_ID
```

PowerShell:

```powershell
$env:FAI_MEDIA_ROOT = 'C:\Users\you\Music'
uv run fusionify-audio analyze 'track.mp3'
```

CLI render commands wait for completion. MCP render tools return a job ID for polling. State defaults to `~/.fusionify-audio`; configure `FAI_STATE_ROOT` to change it. One server process owns each state directory. Use one HTTP server when multiple clients need the same workspace.

## Claude Code plugin

Set `FAI_MEDIA_ROOT` in the environment from which Claude starts, then:

```text
/plugin marketplace add FUSIONIFY-ID/Fusionify_Audio_Intelligence
/plugin install fusionify-audio-intelligence@fusionify-audio
```

Or try a checkout directly:

```bash
claude --plugin-dir /absolute/path/to/Fusionify_Audio_Intelligence
```

Skills included:

- **music-driven-video:** create, revise, render and export edits.
- **audio-intelligence:** inspect actual audio, compare measurements and review/correct beat markers.
- **workspace-setup:** local/remote setup and recovery.

Run `claude plugin validate /absolute/path/to/Fusionify_Audio_Intelligence --strict` for the client CLI's authoritative manifest validation. Repository JSON checks and MCP tests do not substitute for live Claude UI verification.

## Claude Desktop: local MCP

Generate a configuration using actual absolute paths:

```bash
python scripts/configure_client.py --client claude-desktop --media-root /absolute/path/to/media
```

The script prints JSON by default. To merge a chosen configuration file, add `--write /path/to/config.json`. It preserves other server entries and creates a backup. Replacing an existing Fusionify entry requires `--replace`. Set `--uv-command` to the absolute uv executable if your desktop application cannot find it in PATH.

The generated local MCP config does not itself install skills in Desktop. Use the client's available skill installation mechanism separately.

## HTTP workspace and Claude web

Start a local HTTP workspace:

```bash
uv run fusionify-audio generate-token
# Save the generated value securely in FAI_API_TOKEN on your own computer/server.
export FAI_PUBLIC_BASE_URL="http://127.0.0.1:8000"
uv run fusionify-audio serve-http
```

Open `http://127.0.0.1:8000/`, enter the operator-supplied token, and upload music/visuals. The token stays in page memory and is not saved to local/session storage. Copy asset IDs into Claude or create a project through the console.

For a remote connector, deploy behind HTTPS first. Configure:

- URL: your actual `https://your-host/mcp` endpoint.
- Request header: `Authorization` with value `Bearer YOUR_WORKSPACE_TOKEN`, stored in the client's secret configuration rather than chat.
- For Claude web/Desktop, use the custom connector interface. If request headers are unavailable in your client/account, use local mode; do not disable server authentication.

No public service is deployed by cloning this repository. A GitHub URL is not an MCP endpoint. See [deployment](docs/deployment.md) for Docker, HTTPS, imports, and client setup.

## Example conversation

> Pakai asset musik ini dan tiga foto yang sudah diupload. Buat JJ vertikal dengan seluruh durasi musik. Jangan terlalu banyak shake. Buat preview dulu, lalu render penuh setelah timing-nya cocok.

Claude can inspect actual timing, create a saved project, choose a preset/intensity, render an explicitly shortened preview, revise the project, then render its full duration. Photo/video montage scenes use the selected soundtrack; original clip audio is muted. Choose cover (center crop) or contain (letterbox); short video clips may loop. Motion strength is independent of cut density. Validated scene overrides support exact image/clip placement without arbitrary filter code. When too few beat candidates are available, editorial fallback cuts are labeled separately from measured beats.

For custom generated footage, create clips with a separate generation tool, register those files, then assemble them here. This repository does not include a text-to-video generation model or arbitrary per-scene code execution.

## MCP tools

| Flow | Tools |
| --- | --- |
| Workspace and assets | `get_workspace`, `list_media_assets`, `register_media_asset`, `import_media_url` |
| Audio | `analyze_audio`, `get_audio_profile`, `get_audio_timeline`, `compare_audio` |
| Review and correction | `render_beat_preview`, `export_audio_analysis`, `correct_beat_markers` |
| Projects | `create_edit_plan`, `create_video_project`, `get_video_project`, `get_project_timeline`, `list_video_projects`, `revise_video_project` |
| Render and export | `render_video_project`, `render_visualizer`, `get_job_status`, `list_render_jobs`, `cancel_render_job`, `export_video_timeline` |
| Optional provider | `describe_music` |

Use `get_workspace` for current capabilities and limits. Ordinary DSP calls never invoke the optional provider. Returned provider descriptions are uncertain interpretations; measured timestamps remain the timing source.

## Operational limits

- Single trusted owner workspace, not a multi-tenant SaaS. Everyone holding its token can access its assets/projects.
- Per file: 64 MiB; audio/video duration: 180 seconds; image limit: 24 megapixels.
- At most 16 visual assets per project, four queued/active render jobs and one render worker.
- Final render preserves project duration. `preview=true` explicitly uses at most eight seconds and 480-pixel short side.
- Render stages have time limits; completed artifacts persist. Plan storage/cleanup on the host; the application does not automatically delete older user assets or completed work.
- HTTP artifact links expire after ten minutes. Refresh job status or export again for a new link.
- URL imports accept direct public HTTPS media files from exact operator-allowlisted hosts. Redirects are revalidated and the resolved public IP is pinned while TLS verifies the hostname. Streaming pages, private networks and subscription bypasses are unsupported.
- Credentials stay in server/client settings. A chat attachment must be explicitly uploaded or otherwise made accessible to the server.
- No perceptual ground-truth validation of every musical genre, native CapCut/Premiere project export, or generative footage model is claimed.

## Tests

```bash
uv run python -m unittest discover -s tests -v
uv run python tests/mcp_smoke.py
uv run python tests/http_mcp_smoke.py
```

Browser integration, on a host that permits Chromium:

```bash
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```

Tests cover known synthetic beats, silence, file boundaries, URL destination checks, revisions, persistence, cancellation, authenticated uploads/downloads, real media render/audio-offset checks, and actual stdio/HTTP MCP handshakes. Browser tests exercise connect → upload → analyze → project → montage → export → revision on desktop plus responsive checks. Optional Gemini tests are mocked and send no audio externally. Copyrighted music is not included in fixtures.

## References

- [Claude plugin documentation](https://code.claude.com/docs/en/plugins)
- [Claude custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), maintained v1 API used here
- [Gemini audio understanding](https://ai.google.dev/gemini-api/docs/audio)
- [Specification](SPEC.md)
