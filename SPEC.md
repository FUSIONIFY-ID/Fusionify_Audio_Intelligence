# Fusionify Audio Intelligence v0.2

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

Actual public deployment, OAuth, multi-tenant isolation, a built-in generative footage model, variable-tempo beat tracking, production provider evaluation, and perceptual ground-truth alignment across musical styles.

Desktop/Code configurations and remote HTTP deployment code are provided. Actual Claude web/Desktop/Code UI sessions remain separate integration checks; protocol tests alone do not prove client UI compatibility. No public endpoint has been provisioned.

## Validation

Use synthetic click tracks with known pulse positions, silence, file-boundary checks, trim-offset tests, MCP lifecycle tests, and source-file decode/render smoke tests. Do not call a numerical fitting residual proof of perceptual accuracy.
