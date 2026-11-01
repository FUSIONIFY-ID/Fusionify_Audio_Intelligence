---
name: music-driven-video
description: Analyze actual music files and use estimated beats and energy changes to plan JJ, remix, breakbeat, promotional, cinematic, or other music-driven video edits. Use when the user wants to listen to a sound, find timing, synchronize effects, or render a music visualizer with Fusionify Audio Intelligence.
---

# Music-driven video

Use available Fusionify MCP tools. This skill supplies workflow; it does not decode audio by itself.

1. Identify the user's exact audio file. For local MCP, ask for a path inside the configured `FAI_MEDIA_ROOT`. A chat attachment is not automatically accessible to this server. Use an available attachment-transfer tool only when it can actually put the file in that folder.
2. Call `analyze_audio`. Read duration, warnings, and source identity. Do not infer exact timing from a song name or from another remix.
3. Fetch needed sections with `get_audio_timeline`. If truncated, narrow the time range. Treat markers as estimates. Do not equate an energy rise with a confirmed musical drop.
4. Use the full audio duration unless the user requests a shorter range. Never silently shorten the result to 15 seconds. If a request exceeds the source, explain the constraint before introducing looping.
5. Call `create_edit_plan` with the selected music range and intensity. Preserve the source-to-video offset. Choose a restrained effect density where content needs breathing room.
6. For a waveform demo, call `render_visualizer`, then check `get_job_status`. A queued job is not a completed render. A local output path is not a public download link. Use available file presentation tools or tell the user the local path.
7. For footage edits or custom generated scenes, explain that v0.1 returns timing/plans and a fixed visualizer. Use a separately available editing tool if it can implement the requested scenes; do not claim this server already edits arbitrary footage.
8. Request timing feedback on a preview before describing the alignment as verified. State measured observations separately from mood/genre interpretations.

Keep original images and logos unchanged unless the user requests alteration. Keep full-frame flashing off by default. Avoid overclaiming native listening, universal music support, semantic understanding, or exact downbeat detection.

Read [timing.md](references/timing.md) when trimming music, interpreting tempo, or handling uncertain results.
