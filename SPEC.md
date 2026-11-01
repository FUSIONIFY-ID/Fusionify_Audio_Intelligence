# Fusionify Audio Intelligence v0.1

## Product intent

Help creators use externally supplied music to direct the timing of video content through Claude. JJ/remix is the first test case; broader musical and visual styles are the long-term goal. Preserve the exact supplied soundtrack and use its actual waveform rather than a title-based guess.

## Implemented scope

Single-user local MCP over stdio, CLI analysis, bounded timing retrieval, source-relative edit plans, and a background waveform visualizer renderer. Default render duration is the full remaining audio. The skill and Claude Code plugin describe this scope honestly.

## Components

- FFmpeg/ffprobe: bounded, forced-demuxer decoding of files inside the configured media root.
- NumPy/SciPy: spectral-flux onset features, global pulse estimate, waveform energy, and energy-rise candidates.
- MCP Python SDK v1: tool adapter; pinned below v2 because the newer API differs.
- Pillow + FFmpeg: fixed vertical visualizer and original music, no arbitrary code execution.
- Local JSON records: source identity and analysis; in-memory render job status, single active job.

## Current user journey

Configure the media directory, make the file available there, ask Claude to analyze it, review estimated timings, create a plan, then request and review a rendered visualizer. Return a local file path after completion. Do not imply chat attachments transfer themselves.

## Deferred work

Authenticated remote MCP, secure user uploads, hosted preview/downloads, web client testing, multi-user isolation, arbitrary photo/video scene editing, generative footage integration, semantic music understanding, variable tempo tracking, and perceptual beat alignment evaluation.

Desktop/Code local integration configuration is provided. No live Claude UI session is available for end-to-end client validation here. Web compatibility requires the remote deployment phase; no live endpoint exists in this version.

## Validation

Use synthetic click tracks with known pulse positions, silence, file-boundary checks, trim-offset tests, MCP lifecycle tests, and source-file decode/render smoke tests. Do not call a numerical fitting residual proof of perceptual accuracy.
