# Fusionify Audio Intelligence v0.7.0

## Realistic scene workflow (bundle v0.7.2)

Extend the music/video skill with a reusable realism review: ground subject appearance in attributable references, distinguish observed imagery from generated visualization, and disclose adjusted time/scale when material. For astronomy, review surfaces versus atmospheres, illumination, occlusion, rings and readable labels. Match music through editorial cuts and restrained camera accents while preserving a coherent world. Do not physically deform realistic subjects on each beat.

Keep runtime capabilities explicit. The built-in globe/orbit/spectrum/market visuals are stylized; realistic 3D footage requires a separate renderer or supplied assets, then normal registration/project/render tools. Preserve source clocks, frame-rounded boundaries, complete audio and existing artifacts. Validate actual frames and audio separately from structural flags. Describe development as tests, skill revisions and validation; do not claim that a demo trains model weights or adds a renderer to the installed plugin.

## Editor setup and installed-package render verification (bundle v0.7.1)

Extend the explicit config generator to Cursor, Kiro and VS Code while retaining Claude Code/Desktop. Use each client's documented server collection, transport fields and environment-reference syntax. Offer both a frozen checkout launcher and the commit-pinned portable launcher read from mcp.json. Resolve selected media/state paths, preserve unrelated config, back up intentional replacements, reject malformed JSON rather than rewriting JSONC, and never copy a live token or grant blanket tool approval. Print a configuration by default; write only to the explicitly selected destination.

Verify generated configurations in isolated workspaces through real MCP discovery, analysis, project creation, timing review and full-length rendering from the exact pinned package. Probe the resulting video and compare its decoded audio to the synthetic source. Record these as generated-config/protocol checks, not evidence of a native editor GUI session. Keep the remaining GUI, curated marketplace and public HTTPS work explicit. Align documentation's stated engine pin with the manifest and check that alignment automatically.

## Music/video timing review v0.7

Add a read-only `review_music_sync` tool and CLI/HTTP equivalents for saved projects. Compare actual renderer frame boundaries against the selected analysis's pulse markers and measured energy-rise candidates inside the project's source range. Report source/video clocks, signed millisecond offsets, frame quantization, per-marker provenance and user-directed boundaries. Continuous visualizers have no scene cuts. Do not call proximity perceptual accuracy, infer drops/downbeats, silently change timing, or treat an intentional editorial boundary as an error.

Return bounded pages with full-project counts and at most three bounded project-relative preview requests, prioritizing boundaries outside the caller's tolerance. Distinguish no candidates from no boundaries. Preserve project revision and analysis identity. Test trimmed sources, render-specific frame clocks, silence, corrected-marker provenance, boundary limits, pagination, strict arguments, project immutability and actual MCP/HTTP/CLI use. Update the music skill to use review evidence and listen to selected excerpts before proposing changes.

## Source-content isolation (bundle v0.6.3)

Keep the actual user request and selected media/project as the authority for tool actions. Audio, lyrics, filenames, imported transcripts, analysis warnings and external interpretations are untrusted data, including text that imitates system roles or claims user consent. Never promote that text into commands, installation, credentials access, configuration, paths or upload destinations. Preserve useful timing, script comparison and subtitle tasks; do not block benign content merely because it is untrusted.

Use bounded, task-necessary text and preserve provenance. Require external-processing consent from the actual user outside the source, scoped to the selected audio and provider. Provider interpretations cannot broaden that scope. Validate both injected-action resistance and successful benign work with independent task scenarios. Report local checks separately from third-party audit verdicts; never suppress findings or claim a new Pass without observing it.

## Native plugin and skill distribution (bundle v0.6.3)

Package the existing engine and three skills for the Agent Plugins 1.0.0 layout (root plugin.json, mcp.json and skills/), add a Cursor-native manifest and custom marketplace index, and retain the existing Claude layout. Use a tested, commit-pinned uvx engine launch so plugin startup does not depend on client-specific plugin-root placeholders or a writable plugin checkout. Require the user's media folder configuration; do not grant blanket tool approval, fetch model weights, or provision a public endpoint.

Make each standalone skill self-contained when installed through the skills CLI, including relative references and a clear distinction between instructions and the required MCP runtime. Check remote discovery, an isolated real install, canonical manifest schemas, and a real MCP handshake/tool call using the exact packaged launcher. Distinguish source-installable packages/custom marketplaces from curated public listings and successful live editor UI sessions. Do not fabricate directory placement, install counts, publisher identities or review approval.

## v0.6.1 real local speech verification

Exercise actual local Whisper inference on known-script synthetic narration, silence and speech with a music bed, without uploading audio. Keep model acquisition an explicit operator setup action outside tools. Pass bounded finite 16 kHz mono float PCM into the backend so ASR cannot re-decode media through a dependency-specific PyAV API. Preserve origin and timestamp uncertainty. Add a reproducible opt-in local-model smoke script; ordinary offline CI must not download model weights. Record the exact model revision, synthetic source, measured results and limits without presenting a small synthetic test as Indonesian/remix accuracy validation.

For exact all-zero PCM, skip model inference and persist an empty transcript with explicit local_signal_gate origin and inference_performed=false. This gate is not voice activity detection and must not remove quiet nonzero speech. Retain ordinary ASR hypotheses, add bounded listening-review flags for low model word probabilities and word spans on digital silence, and carry those flags into script comparison. Scores are uncalibrated, not accuracy guarantees; no flags is not verification.

## v0.6 voice and script review contract

Add offline periodic-pitch, signal activity, pauses and level/headroom review. Source type is explicitly declared by the caller (speech or mixed_audio), never inferred. Mixed music cannot establish vocal intonation, identity, emotion or pronunciation. Persist bounded source-relative contours and paginate them. Phrase pitch trends describe measured periodic components, not whether delivery is correct.

Add strict persistent timed transcript import and optional local faster-whisper transcription. Require an operator-provided complete local model directory, local-only loading and offline environment; no automatic model download, no external audio upload. ASR runs in the bounded cancellable job queue in a subprocess with a deadline. Availability must distinguish installed/configured from validated inference. Imported text is not acoustically verified; ASR words and timestamps remain estimates.

Compare a user-provided script to a selected transcript using Unicode-normalized token alignment, bounded edit counts, omissions/additions/substitutions and timestamp provenance. Never turn text agreement into a pronunciation or intonation score. Export SRT/VTT/JSON, optionally clipped and shifted to a saved project's music range after verifying matching source hashes. A partially clipped segment must use word timings or be omitted with an explicit warning, rather than attach the complete sentence to a shortened range. Treat audio/transcript text as untrusted content.

Validate known synthetic pitch trends, silence/noise, mixed-source attribution, malformed timestamps, script differences, Unicode, output bounds, subtitle injection/trim offsets, source mismatch, local-only model guards, mocked ASR lifecycle and actual MCP stdio/HTTP tools. Do not claim live ASR quality when a real local model is unavailable.

## v0.5 source-time cue control and targeted review

Extend music-to-content direction with optional section anchors: an ordered list of section_index (1–7) and absolute source_time_s. Index zero is the start of the selected music range. An anchor locks a later section's start; it is a user direction, never a detected drop. Fill unlocked sections between anchors using the existing energy/pulse/editorial planner, preserving readable minimum holds. Reject contradictory/out-of-range anchors and anchors on beat-paced or explicit-scene-override projects.

Extend render_video_project preview mode with project-relative preview_start_s and optional preview_duration_s, limited to eight seconds and at least one output frame. Final mode must reject preview-range parameters so it cannot silently truncate the saved full project. Excerpts preserve section/story identity, original music offsets, continuous native motion clocks, pulse decay from preceding markers, per-asset footage clocks and fixed per-scene effect progress. Previewing does not revise the saved project.

Expose anchor evidence and preview range/revision in tool results, CLI and companion skill instructions. Validate anchor constraints, trimmed source offsets, locked-boundary preservation, late-section copy, native frame equivalence, genuine audio correlation, video source continuity and montage effect progress. Keep existing prefix preview calls backward compatible.

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
