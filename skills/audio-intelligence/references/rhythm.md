# Rhythm correction examples

All timestamps below refer to the exact source, before a project's music trim.

Known changing tempo example (source must be at least 30 seconds):

```json
{
  "analysis_id": "ACTUAL_ANALYSIS_ID",
  "regions": [
    {"start_s": 0, "end_s": 12, "bpm": 120, "first_beat_s": 0.4},
    {"start_s": 12, "end_s": 30, "bpm": 160, "first_beat_s": 12.15}
  ],
  "snap_tolerance_s": 0.03
}
```

Use `apply_tempo_map` only with the user's timing directions or explicitly described editing assumptions. Inspect marker provenance in `get_rhythm_review`, then use the returned new analysis ID for `render_beat_preview` and `create_video_project`. Do not switch an existing project silently.

For a constant 128 BPM track whose first chosen beat is 0.45 seconds, use one region starting at zero and ending at the actual measured source duration, with `first_beat_s: 0.45`. Grid beats begin at that anchor; no beats are backfilled before it. To halve/double a chosen grid, adjust its BPM within the supported range; this changes editing pulse density, not the original audio speed.

Tap example: `estimate_tap_tempo({"tap_times_s": [0.4, 0.9, 1.4, 1.9, 2.4]})`. The returned estimate is about 120 BPM. It is a read-only estimate and does not change the analysis. Ask for a retry when taps are rejected; do not invent timestamps to force acceptance.

The browser console's Review music timing section supports original/click playback, source-relative seeking, a zoomable waveform range, marker add/remove, undo/reset and saving a timing copy. Its tempo grid control covers one full-source region; use MCP for multiple regions. Unsaved marker edits must be saved or reset before project creation/rendering or grid replacement.

Each saved copy has a parent analysis ID. Manual-marker edits after a tempo map clear the old tempo-map metadata because it no longer describes the edited marker list. Original DSP measurements remain available and are never rewritten by timing corrections.
