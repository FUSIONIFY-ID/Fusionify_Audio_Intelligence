# Creator options and tool map

Project options:

```json
{
  "title": "Fusionify Bot",
  "caption": "Your next order, in motion.",
  "style": "jj",
  "intensity": "medium",
  "aspect": "9:16",
  "resolution": 720,
  "music_in_s": 0,
  "duration_s": null,
  "asset_ids": [],
  "audio_gain_db": 0,
  "motion_amount": 0.6,
  "fit_mode": "cover",
  "scene_overrides": []
}
```

- `duration_s: null`: use the full remaining audio. Maximum source length: 180 seconds.
- Styles: `jj`, `cinematic`, `promo`, `minimal`. Intensity: `low`, `medium`, `high`.
- Aspects: `9:16`, `16:9`, `1:1`. Resolution is the short side: 480, 720, or 1080 pixels.
- Asset IDs must reference registered images/videos, at most 16 per project. Images and video are scaled and center-cropped to the selected output ratio. Video clips can loop when their allocated scene exceeds their duration.
- Audio gain ranges from -18 to +6 dB; default zero retains source level. Positive/negative adjustments invoke a limiter, so adjusted sound is not bit-identical.
- `motion_amount` ranges from 0 to 1 and independently controls zoom/pan/shake strength. Reduce this value to soften motion while retaining JJ pacing; zero disables those movements.
- `fit_mode` is `cover` (center crop) or `contain` (letterbox). Use `contain` plus zero motion when the whole source image/logo must remain visible.
- Scene effects are selected from fixed cut/zoom/pan/shake presets; there is no arbitrary filter/code field.
- `music_in_s` shifts source-relative beat positions onto the video timeline.
- Job results persist across restart. Active jobs become `interrupted` after a restart and must be resubmitted. A queue holds at most four active/queued jobs, with one render worker.
- HTTP downloads expire after ten minutes. Refresh `get_job_status` or export again for a fresh link. Do not expose tokens in a prompt, source file, shared screenshot, or URL.

Example revision: “Reduce shake” → read project, lower `motion_amount` and optionally `intensity`, preserve other options, then render the new revision.

To explicitly place a visual at a chosen video time, supply `scene_overrides`: a full contiguous list of `{start_s, end_s, asset_id, effect, video_in_s}` scenes. Effects are cut/zoom/pan/shake. Every asset must also be selected in `asset_ids`; scenes must cover the exact selected project duration starting at zero, with at least one frame per scene. `video_in_s` defaults to zero and must be within the video; images require zero. No executable code or filter strings are accepted.

When there are too few beat candidates to show all selected visuals, the automatic builder uses an equal editorial split and reports `scene_boundary_source`. Those boundaries are not represented as measured beats. Explicit user scenes can intentionally reuse only a subset of selected assets.

v0.4 options: `pacing_mode` is `beat` (compatibility default) or `musical` (readable editorial holds separate from beat accents). `visual_mode` is `auto` or `motion_graphics`. `text_overlay: false` suppresses additional montage copy. `video_playback` is `continue` (per-asset playback clock) or `source_sync` (source music offset plus current video time), with explicit scene `video_in_s` taking precedence. Clips still loop if their usable source is too short. The native route accepts `brand` (40 characters), `accent_color` (lime/blue/coral), `content_brief` (300 characters) and up to eight `story_blocks` of headline/support/visual. Visuals are globe/spectrum/orbit/market. See [direction.md](direction.md) for content selection and limitations.

Use `create_music_direction` before saving, and `review_content_fit` before delivering the render. Their creative/structural checks are not perceptual or semantic accuracy scores.
