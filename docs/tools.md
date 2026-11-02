# MCP tools and workspace limits

[← Back to the overview](../README.md) · [Editing workflows](workflows.md)

The current server exposes **37 tools**. Call `get_workspace` to inspect the running server's capabilities and configuration.

## Tool map


| Flow | Tools |
| --- | --- |
| Workspace and assets | `get_workspace`, `list_media_assets`, `register_media_asset`, `import_media_url` |
| Audio | `analyze_audio`, `get_audio_profile`, `get_audio_timeline`, `compare_audio` |
| Review and correction | `render_beat_preview`, `export_audio_analysis`, `correct_beat_markers` |
| Rhythm editing | `get_rhythm_review`, `estimate_tap_tempo`, `apply_tempo_map` |
| Content direction | `create_music_direction`, `review_content_fit`, `review_music_sync` |
| Projects | `create_edit_plan`, `create_video_project`, `get_video_project`, `get_project_timeline`, `list_video_projects`, `revise_video_project` |
| Render and export | `render_video_project`, `render_visualizer`, `get_job_status`, `list_render_jobs`, `cancel_render_job`, `export_video_timeline` |
| Voice and script | `analyze_voice`, `get_voice_timeline`, `transcribe_audio`, `import_transcript`, `get_transcript`, `check_spoken_text`, `export_transcript` |
| Optional provider | `describe_music` |

Use `get_workspace` for current capabilities and limits. Ordinary DSP calls never invoke the optional provider. Returned provider descriptions are uncertain interpretations; measured timestamps remain the timing source.

## Operational limits

- Single trusted owner workspace, not a multi-tenant SaaS. Everyone holding its token can access its assets/projects.
- Per file: 64 MiB; audio/video duration: 180 seconds; image limit: 24 megapixels.
- At most 16 visual assets per project, four queued/active render jobs and one render worker.
- Final render preserves project duration. `preview=true` explicitly uses at most eight seconds and 480-pixel short side, clipping the saved sequence at the requested project-relative start rather than rearranging the story over a shorter range.
- Render stages have time limits; completed artifacts persist. Plan storage/cleanup on the host; the application does not automatically delete older user assets or completed work.
- HTTP artifact links expire after ten minutes. Refresh job status or export again for a new link.
- URL imports accept direct public HTTPS media files from exact operator-allowlisted hosts. Redirects are revalidated and the resolved public IP is pinned while TLS verifies the hostname. Streaming pages, private networks and subscription bypasses are unsupported.
- Credentials stay in server/client settings. A chat attachment must be explicitly uploaded or otherwise made accessible to the server.
- No perceptual ground-truth validation of every musical genre, native CapCut/Premiere project export, or generative footage model is claimed.

