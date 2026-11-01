# Fusionify Audio Intelligence v0.4

## v0.4 music-to-content direction contract

The music skills must translate measured timing plus the user's content brief into a coherent edit. Review the music and content goal → propose a music direction plan → distinguish large editorial scene changes from small pulse reactions → supply story copy/visual motifs → preview → revise → render full duration. Preserve the approved first globe demo's clear typography, continuous motion and sparse scene hierarchy. Do not recycle that finished demo as footage under another full-frame title.

Add `create_music_direction`: read-only source-relative section proposals and explicit evidence, energy measurements, content brief and small-motion accent counts. Editorial opening/development/closing roles are creative proposals, never detected musical sections or verified drops. Silence has no invented beat accents. Boundaries can use nearby measured/user timing; editorial boundaries remain labeled as such.

Saved projects gain opt-in musical pacing and a native procedural motion-graphics renderer with user-supplied story blocks (headline, supporting copy, globe/spectrum/orbit/market visual). Motion uses a continuous project clock and actual audio samples/spectrum. Market charts are explicitly audio-derived illustrations, never business transaction data or geographic analytics. Typography stays within safe margins; no extra title is drawn over a composed motion scene. Existing v0.3 projects keep their default beat pacing/visualizer behavior.

Montages gain an explicit overlay switch and source-synchronized footage playback. Existing continue-playback remains the default. No arbitrary user code or filter strings. Validate scene holds versus pulse counts, source/video offsets, provenance, quiet/silent tracks, narrative coverage, native renders, continuous motion time, text bounds and original soundtrack correlation. Render a full-length demonstration through the installed project service, not an independent one-off script.

## v0.3 rhythm editing contract

Extend the existing timing-review flow: select an uploaded soundtrack → inspect a bounded waveform with source-relative markers → prepare original or click-overlay audio → seek/listen → add/remove markers or supply BPM/first beat → save a new timing analysis → create/render a project from that analysis. Editing must never silently overwrite the original analysis or the timing of an existing project. Warn before using unsaved marker edits.

Add `estimate_tap_tempo` (read-only, ordered source-relative taps, robust interval summary rather than an accuracy claim), `apply_tempo_map` (immutable derived analysis from validated non-overlapping source-relative tempo regions), and `get_rhythm_review` (bounded waveform peaks and complete markers, without filesystem paths). Tempo maps support known tempo changes; they are user directions, not automatic variable-tempo detection. Optional snapping only uses nearby measured onset candidates and retains per-marker provenance; unmatched grid points remain explicitly user-specified. Regions use half-open bounds, and gaps deliberately contain no map beats.

Extend `render_beat_preview` with bounded click volume (zero gives original audio without gain change) while preserving its default behavior and full duration. The console controls playback, zoom/range, marker selection/add/remove, undo/reset of unsaved edits, and single-region tempo input; multi-region maps are available through MCP/CLI. Keep all existing project and rendering flows working.

Validate known fixed and changing tempo maps, offsets, end/gap boundaries, snap limits, tap jitter/outliers, malformed inputs, immutable analysis lineage, marker provenance in plans/exports, real audio duration/correlation, MCP stdio/HTTP discovery/calls, and browser listen → seek → edit → save → project → render workflows on desktop/mobile.

## v0.2 implementation contract

Extend the validated local engine into a complete creator workspace: ingest permitted media, analyze actual audio, inspect/correct timing, persist and revise an edit project, render original music with selected photos/video clips, then preview/download results. Keep full source duration by default.

Add authenticated Streamable HTTP alongside stdio, a same-origin upload/preview console, short-lived signed artifact links, restricted HTTPS file imports, persistent assets/projects/jobs, cancellation, preview rendering, marker exports, and Docker deployment instructions. The HTTP deployment is one trusted owner workspace, not a multi-tenant SaaS. Never expose an unauthenticated owner endpoint.

Tool flows: register/list/import assets → analyze/get timeline/correct beats → create/get/revise project → render/poll/cancel → export/download. The console is a companion upload and preview surface; conversation remains the main way to direct edits.

Support fixed named styles (jj, cinematic, promo, minimal), selected beat density, cut/zoom/pan/shake effects, 9:16/16:9/1:1 output, bounded resolutions, user photos and MP4 clips, title/caption overlays, and original audio. Accept declarative validated data only. No model-generated shell commands, Python, or FFmpeg filter strings.

Validation must include real stdio and HTTP MCP handshakes, denied authentication, signed-link expiry/tampering, local path and DNS/IP boundary checks, project revision conflicts, persistence after restart, media render/decode and audio offset checks, plus the existing DSP tests.

Live public HTTPS deployment and live Claude UI testing require a chosen host and are not claimed by repository tests. DSP does not establish genre, mood, lyrics, or perceptual beat accuracy. No subscription streaming bypass or copyrighted media is bundled in the repository.

## Product intent

Help creators use externally supplied music to direct the timing of video content through Claude. JJ/remix is the first test case; broader musical and visual styles are the long-term goal. Preserve the exact supplied soundtrack and use its actual waveform rather than a title-based guess.

## Implemented scope

Single-owner workspace with local stdio and authenticated HTTP MCP, uploads, allowlisted imports, measured audio analysis, manual timing corrections, persistent revisable projects and render jobs, waveform and footage montage rendering, fixed motion effects, contain/cover fitting, explicit scene overrides, and artifact exports. Default project duration is the full remaining audio. The optional Gemini adapter requires explicit external-processing consent and server configuration; offline provider tests are mocked.

## Components

- FFmpeg/ffprobe: bounded, forced-demuxer decoding of files inside the configured media root.
- NumPy/SciPy: spectral-flux onset features, global pulse estimate, waveform energy, and energy-rise candidates.
- MCP Python SDK v1: tool adapter; pinned below v2 because the newer API differs.
- Pillow + FFmpeg: fixed vertical visualizer and original music, no arbitrary code execution.
- SQLite records: assets, analyses, projects with revisions, jobs and artifacts. One bounded worker, up to four active/queued jobs, process lock per state directory.

## Current user journey

Configure a local or hosted workspace, upload/register music and selected photos/videos, analyze timing, optionally review/correct markers, create a saved project, explicitly preview, revise, and render the full project. Return actual local paths or expiring signed HTTP artifact links. Do not imply chat attachments transfer themselves.

## Deferred work

Actual public deployment, OAuth, multi-tenant isolation, a built-in generative footage model, automatic variable-tempo beat tracking, production provider evaluation, and perceptual ground-truth alignment across musical styles. Explicit user-directed tempo maps are implemented in v0.3.

Desktop/Code configurations and remote HTTP deployment code are provided. Actual Claude web/Desktop/Code UI sessions remain separate integration checks; protocol tests alone do not prove client UI compatibility. No public endpoint has been provisioned.

## Validation

Use synthetic click tracks with known pulse positions, silence, file-boundary checks, trim-offset tests, MCP lifecycle tests, and source-file decode/render smoke tests. Do not call a numerical fitting residual proof of perceptual accuracy.
