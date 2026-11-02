# Music-to-video workflows

[← Back to the overview](../README.md) · [Tool reference](tools.md) · [Voice and script review](voice-review.md)


## Place a message at a chosen moment in the music

Use `section_anchors` in saved musical-pacing projects and `create_music_direction`. An anchor is `{ "section_index": 2, "source_time_s": 17.425 }`: section indices are zero-based, so this locks the third section to second 17.425 of the original audio file. The first section implicitly begins at `music_in_s`. Indices 1–7 are available when those later sections exist. Anchors must be ordered, inside the selected source range, and leave readable holds. They are user directions, not automatically detected drops. Explicit scene overrides and section anchors are separate alternative timing methods.

To keep other scene timing unchanged during a cue revision, read `get_project_timeline.music_sections` and anchor the other later boundaries too. Unlocked sections are replanned between locks. Reordering story blocks requires deliberate index remapping. Too many selected assets for an anchored section count is rejected rather than redistributing and losing the locked times.

Review the changed moment using `render_video_project` with `preview: true`, project-relative `preview_start_s`, and `preview_duration_s` from one frame to eight seconds. For a project beginning at audio second 5, a source cue at 17.425 appears at video second 12.425; a six-second preview beginning 1.5 seconds before it uses start 10.925. Excerpts retain story identity, the original graphic/footage clocks, preceding pulse decay and per-scene motion progress. Native display time remains the full project's clock. Frame-based output still has 30 fps quantization.

Preview queue/status results report project ID, saved revision and selected range. The saved project remains unchanged. Full rendering uses `preview: false` with no preview-range parameters; incompatible parameters are rejected to prevent accidental truncation. Never revise the saved music range merely to review an excerpt.

```bash
uv run fusionify-audio music-direction ANALYSIS_ID --anchors anchors.json
uv run fusionify-audio render-project PROJECT_ID --preview --preview-start 10.925 --preview-duration 6
uv run fusionify-audio render-project PROJECT_ID
```

Cue control and targeted ranges are currently available through MCP/CLI. The console's existing preview button still reviews the opening.

## Match the music to the content

The music skill guides the edit's direction: resolve the content goal, inspect actual music, call `create_music_direction`, choose readable story holds separately from ordinary beat accents, save a project, call `review_content_fit`, inspect a preview, then render full length. Section roles are creative proposals. A content brief is recorded for the host assistant; the DSP algorithm does not understand product meaning or judge artistic quality.

For a graphic story without footage, save a project with `visual_mode: "motion_graphics"`, `pacing_mode: "musical"` and `story_blocks` containing `headline`, `support`, and `visual` (`globe`, `spectrum`, `orbit`, or `market`). Native graphics use a continuous project clock, actual waveform/spectral data and a single composed text layer. Up to eight blocks are supported; a very short range may require fewer blocks to keep them readable. `brand` and `accent_color` (lime/blue/coral) customize the composition.

For an already designed clip, set `text_overlay: false` to avoid adding a second title. If the clip is already synchronized to the exact selected soundtrack, `video_playback: "source_sync"` uses music source time plus video time instead of slowing its progression between still images. Explicit scene in-points take precedence. Short clips can still loop; this option cannot manufacture missing footage. Existing projects keep their beat-pacing/per-asset-clock defaults.

Native `market` graphics are explicitly labeled audio-derived illustrations. They are not real transactions, geographic analytics or market prices. Supply actual business evidence separately; do not invent proof from a music waveform. `review_content_fit` reports structural risks and does not claim to see pixels or validate subjective synchronization.

Native graphics implement the small pulse reactions inside held scenes. Montage musical pacing controls its major scene boundaries; supplied footage retains fixed per-scene cut/zoom/pan/shake motion rather than gaining a reaction on every beat.

CLI: `uv run fusionify-audio music-direction ANALYSIS_ID --brief "Introduce the product, then close with its name"`. Use `create-project --options options.json` for the native story. The companion console retains its established upload/rhythm/montage controls; advanced story direction is currently through MCP or CLI.

## Review saved cut timing

Use `review_music_sync` to compare saved scene cuts with pulse and energy-rise candidates on the actual full-render frame clock. Inspect source/video offsets, provenance and locked cues, then listen to suggested project-relative excerpts. The tool is read-only; a distant candidate does not invalidate an intentional story cut. See [timing review](sync-review.md) for pagination, tolerance and preview arguments.

## Review and correct rhythm

Open **Review music timing** in the console, load the waveform, and prepare original audio or a click preview. Listen/seek, zoom the displayed source range, add/remove markers, and undo/reset unsaved changes. **Save timing copy** creates a new analysis and makes it the source for the next new project; existing projects retain their original timing. Unsaved marker edits block project creation/rendering until saved or reset. Preparing original audio retains its level; click previews lower music to 78 percent and mix soft markers. MP3 previews are re-encoded, not bit-identical to the source.

The tempo-grid controls accept BPM and an absolute source-relative first beat over the full soundtrack. Tap at the playing audio's playhead at least four times for an estimate, then explicitly save a grid if wanted. For multiple BPM regions, use MCP `apply_tempo_map` or CLI:

```bash
uv run fusionify-audio tempo-map ANALYSIS_ID --regions regions.json --snap 0.03
uv run fusionify-audio rhythm-review NEW_ANALYSIS_ID
uv run fusionify-audio beat-preview NEW_ANALYSIS_ID --click-volume 1
```

`regions.json` is an ordered array, for example `[{"start_s":0,"end_s":12,"bpm":120,"first_beat_s":0.4},{"start_s":12,"end_s":30,"bpm":160,"first_beat_s":12.15}]` for a source at least 30 seconds long. Regions cannot overlap, each first beat is inside its region, end timestamps are exclusive, and gaps contain no grid markers. Snapping is optional, bounded to 0.1 seconds and only uses nearby measured onsets. Use the returned new analysis ID for subsequent previews/projects. `tap-tempo taps.json` accepts 4–128 ordered source-relative tap times and does not save timing itself.

## Create a video

> Pakai asset musik ini dan tiga foto yang sudah diupload. Buat JJ vertikal dengan seluruh durasi musik. Jangan terlalu banyak shake. Buat preview dulu, lalu render penuh setelah timing-nya cocok.

Claude can inspect actual timing, create a saved project, choose a preset/intensity, render an explicitly shortened preview, revise the project, then render its full duration. Photo/video montage scenes use the selected soundtrack; original clip audio is muted. Choose cover (center crop) or contain (letterbox); short video clips may loop. Motion strength is independent of cut density. Validated scene overrides support exact image/clip placement without arbitrary filter code. When too few beat candidates are available, editorial fallback cuts are labeled separately from measured beats.

For custom generated footage, create clips with a separate generation tool, register those files, then assemble them here. This repository does not include a text-to-video generation model or arbitrary per-scene code execution.

