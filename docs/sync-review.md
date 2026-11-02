# Review cut timing against music

Engine v0.7 adds a read-only review for saved montage and native motion-graphics projects. It helps locate cuts worth listening to before changing an edit. It does not upload audio, revise projects or automatically snap cuts.

Call `review_music_sync` with the saved `project_id`. The default review tolerance is 80 milliseconds; choose 0–250 ms for your task. The result identifies the analysis, project revision, selected music range and renderer. Pulse markers and energy-rise candidates are restricted to that source range.

Each boundary includes:

| Field | Meaning |
| --- | --- |
| `requested_video_time_s` | The saved editorial cut time. |
| `video_time_s` / `frame_index` | The full-render cut on the 30 fps frame clock. |
| `source_time_s` | Rendered video time plus the soundtrack's `music_in_s`. |
| `frame_shift_ms` | Renderer quantization relative to the requested cut. |
| `nearest_pulse` / `nearest_energy_rise` | Separate candidate matches and their provenance. |
| `offset_ms` | Cut minus candidate. Positive is after; negative is before. |
| `user_directed` | A saved explicit scene override or locked story cue. |

For example, a montage cut requested at video second 1.01 renders at frame 30, or second 1.00. With a music in-point of 2 seconds, its source timestamp is 3.00. A pulse at source second 2.98 yields a **+20 ms** offset. Native story sections use the first frame on/after their requested boundary, so their quantization can differ from montage rounding.

`near_reference` means within the chosen tolerance, `outside_tolerance` means farther away, and `no_reference` means no candidate is available. These are review categories, not correct/incorrect judgments or an accuracy percentage. A deliberate narrative cue may belong between beats. User grid markers are not independent measurements. Missing candidates do not prove silence or the absence of rhythm. The check reads saved analysis and does not verify current source bytes or perceptual synchronization.

`offset` and `limit` paginate boundary rows, up to 100 per call. Counts always describe the full project. At most three `suggested_previews` offer project-relative listening windows up to four seconds. Recheck the current project revision, then pass only `project_id`, `preview`, `preview_start_s` and `preview_duration_s` to `render_video_project`. Poll the job and verify its revision before interpreting the excerpt. The remaining suggestion fields are metadata. A continuous waveform visualizer correctly reports `no_scene_boundaries`.

CLI:

```bash
uv run fusionify-audio review-sync PROJECT_ID --tolerance-ms 80 --offset 0 --limit 100
```

The authenticated HTTP console API accepts operation `review_music_sync` with the same arguments. MCP and CLI are the current user-facing routes for this review; no new console controls are included. Existing content-fit and rhythm-review tools remain complementary: they cover structural risks and the soundtrack's marker list, respectively. Listen to actual excerpts and preserve the content brief when deciding whether to revise.
