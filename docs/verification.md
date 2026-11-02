# Verification notes

## Music/video cut timing review v0.7

Eight new tests cover trimmed source clocks, renderer-specific frame quantization, signed offsets and tolerance boundaries, in-range candidate filtering, user marker provenance, locked cues, no-reference/continuous-visualizer cases, skipped zero-frame montage scenes, bounded pagination/previews, strict arguments, project immutability, persistence and CLI use. The backend suite now contains 56 tests. Actual montage encoding confirms a requested 1.01-second cut changes from red to blue at frame 30, matching the diagnostic's 1.00-second render time. Native `MotionFrames.state` is checked immediately before and at its reported first section frame.

Real stdio and TCP Streamable HTTP MCP smoke flows call `review_music_sync` on saved native projects, including source offsets, locked boundaries and pagination; stdio also checks boolean argument rejection. The authenticated HTTP console API checks no-boundary behavior and malformed tolerance. The server now exposes 37 tools. A fresh agent using only the revised music skill and a recorded task preserved user-directed cues, distinguished early/late candidate offsets from a subjective complaint, proposed revision-checked local preview calls, and made no automatic edits or external-processing claim.

These checks establish deterministic timing/reporting behavior on synthetic fixtures. They do not prove human-perceived sync on the user's music, identify true drops/downbeats, validate current audio bytes, or establish semantic video quality. The new review is available through MCP/CLI/HTTP API, with no new console controls. External security audit verdicts remain separate.

## Source-content isolation, bundle v0.6.3

Three independent recorded-task checks covered injected timing metadata, scoped Gemini consent with injected provider output, and a benign imported-transcript/subtitle flow. All preserved task scope and provenance while allowing legitimate work. These are instruction-following checks, separate from runtime tests and external audit verdicts. See [security audit evidence](security-audits.md) for the observed baseline, policy changes and limitations.

## Native plugin distribution checks

Plugin bundle v0.6.2 supplies root Agent Plugins manifests and a Cursor-native plugin/marketplace index, packaging the three skills with a commit-pinned uvx launcher. Canonical Agent Plugins 1.0.0 schema checks and standalone reference containment checks are available through `scripts/validate_distribution.py`. The separate `tests/distribution_smoke.py` exercises the exact launch command, initializes a real MCP session, discovers 36 tools, analyzes an eight-second synthetic click track and requests music direction. The backend unit count remains 48; distribution checks are additional integration checks.

The skills CLI discovers all three existing public skills. Individual skills now keep their relative references inside their own directories, and explain the separately required MCP runtime. Source-installable packaging is not evidence of acceptance into a curated public marketplace, a skills.sh ranking, or successful native editor GUI sessions. No store publication or public HTTPS endpoint is claimed.

## Real local-model check v0.6.1

A real local run exposed a decoder failure: faster-whisper 1.2.1 called PyAV with `metadata_errors`, rejected by PyAV 19.0.2. v0.6.1 passes bounded, validated 16 kHz mono float32 arrays directly to the backend. No PyAV re-decoding is required for inference. The runtime tested was Python 3.12.14, faster-whisper 1.2.1, CTranslate2 4.8.4 and NumPy 2.5.4, on CPU/int8 with two threads.

Model: [Systran/faster-whisper-tiny](https://huggingface.co/Systran/faster-whisper-tiny/tree/d90ca5fe260221311c53c58e660288d3deb8d356), revision `d90ca5fe260221311c53c58e660288d3deb8d356`. The 75,538,270-byte model.bin was verified against the publisher's LFS SHA-256 `dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1`. Weights were prepared separately for operator QA, not downloaded by an application MCP tool or committed to the repository.

The source is FFmpeg libflite `slt` reading the 13-word English script embedded in `tests/local_speech_smoke.py`. Beds combine synthetic tones and a pulse, scaled relative to narration RMS. Actual observed results:

| Fixture | Duration | Script differences | Low-probability word flags |
| --- | --- | --- | --- |
| Clean narration | 4.70503 s | 1 substitution, test → cast, WER 0.07692 | 1 |
| Bed at 0.125 × narration RMS | 4.70503 s | 1 substitution, test → cast, WER 0.07692 | 1 |
| Bed at equal narration RMS | 4.70503 s | 0 edits on this sample | 1 |
| Exact digital silence | 5 s | Empty transcript, inference bypassed | 0 |

Raw ASR initially hallucinated “You” on the all-zero fixture, with word probability about 0.019. The new exact-zero gate returns `local_signal_gate` provenance with no inference. It does not filter quiet nonzero audio or establish that arbitrary noise has no speech. Low model probabilities and exact-zero word spans generate bounded listening flags; they do not rewrite text or establish errors. On the clean fixture, the low-probability word was “timing”, while the actual script difference was “cast”. This demonstrates why a confidence flag cannot substitute for script comparison.

The three narration cases exported subtitles against a project starting at source second 1 for two seconds, checking all exported cue bounds and reporting crossing-word omissions. The opt-in script also runs actual local-model transcription, persistent job polling, script comparison and SRT export through MCP stdio. Timings remain estimates: no phoneme-alignment ground truth, Indonesian voice, human narrator, singing or real remix benchmark was evaluated. The equal-bed case does not imply that adding louder music improves recognition.

Two additional regression tests (48 total) verify digital-silence provenance/no model construction, bounded review flags and preservation of hypotheses. The existing backend-construction test now verifies array input and rejects invalid rate, channel count and nonfinite PCM. Default CI does not fetch model weights; repeat real QA explicitly with the opt-in script and a compatible local model.

## v0.6 voice/script review

Nine added tests (46 total) cover known synthetic rising/falling/level pitch, noise/silence, quiet gaps, full-scale review flags, mixed-source attribution, strict transcripts, Unicode alignment, omissions/additions/substitutions, missing-word timestamps, comparison bounds, subtitle escaping, trim/offset semantics, source mismatches, persistence, pagination, mocked ASR queue results/cancellation and offline backend construction. Stdio and real TCP HTTP smoke scripts exercise the new voice/transcript tools and project-relative subtitle download. MCP exposes 36 tools; three companion skills are updated.

The optional faster-whisper package was installed and its real WhisperModel class imported successfully. Local ASR model construction and inference responses in tests are mocked. At the initial v0.6 release no real model had been tested; the limited v0.6.1 local-model checks above now supplement these mocked tests. General transcription and word-alignment quality remain unverified. Configuration flags only establish readiness to attempt. Synthetic pitch checks do not prove real vocal intonation accuracy, especially in mixed music. No pronunciation/emotion scoring or automatic correction is implemented. Subtitle sidecars are exported, not burned into the video.

## Locked cues and targeted review

v0.5 adds seven tests (37 total); the MCP tool count remains 29. Coverage includes source-relative anchors after a music trim, ordered/readable constraints and incompatible modes, preserving locked boundaries after ordinary project revision, and validating that preview parameters cannot silently shorten a final render.

Targeted native frames are compared directly against the corresponding full-timeline frames, including story block, header, original project clock, waveform, beat-decay strength and graphic position. A real native excerpt is encoded and its audio is correlated against the correct original source region. Two colored-footage checks establish that continue and source_sync modes use their distinct expected source offsets after intervening images. A real zooming-grid render compares the excerpt against the corresponding full-render image, checking that zoom progress does not restart.

Stdio and TCP HTTP MCP smoke scripts exercise source-time anchors and targeted native previews, including queued/completed project revision/range metadata and signed hosted output links. Existing opening-preview/browser behavior remains a regression check. Offline tests do not claim live Claude application UI compatibility or perceptual sync accuracy.

## Music-to-content direction

v0.4 adds five backend tests (30 total), two MCP tools (29 total), a source-evidence/editorial direction planner, native procedural graphics and content-fit checks. Added tests cover readable sections versus many micro accents, source offsets, eligible energy-rise preference, silence, continuous clocks across scene boundaries, bounded text in 9:16/16:9/1:1, actual native encoding and audio correlation, preview prefix preservation and source-synchronized clip playback without an overlay. A regression case reproduces rapid cuts, possible duplicate titles, mixed-media clock drift and short-clip loops; after the relevant option fixes, only the genuine short-source risk remains.

The native renderer is fixed application code. It does not run model-generated code. Its market visual is an explicitly labeled audio-derived illustration, not sales, geographic or financial data. The host assistant chooses story meaning from the user brief. Structural checks and numerical timing/audio tests do not establish subjective content quality or perceptual beat correctness.

Advanced v0.4 direction is currently through MCP/CLI. Existing console controls are kept compatible and the browser workflow remains a regression check; no new UI controls are claimed. The full-length demonstration is rendered through Service.create_project/render_project using the user's actual sound rather than an independent renderer outside the package.

## Backend and protocol checks

The automated suite covers 48 tests for synthetic pulses and silence, decode boundaries, path/symlink restrictions, malformed authorization, signed download expiry/tampering, upload validation, revisions, persistence, cancellation, manual markers, explicit scenes, config merging, montage render/audio offsets and mocked provider contracts. New rhythm coverage includes ordered tempo regions, exclusive boundaries/gaps, strict numeric inputs, nearby-onset snapping, tap jitter/outliers, immutable analysis lineage, complete waveform bins, project marker provenance and original/click preview duration/audio level. Separate smoke scripts exercise actual MCP initialization/discovery/calls over both stdio and TCP Streamable HTTP, including the three new rhythm tools (36 tools total).

Waveform/MP3 and image/video montage outputs are decoded and probed, including short video looping and music in-points. Audio correlation checks use a known synthetic source; they do not establish perceptual alignment for every musical style. A package build also verifies the HTML/CSS/JS console is included in the wheel.

The Claude CLI manifest validator is run with `--strict`. Its plugin-directory profile is a different check: official directory submission still needs an owner-selected license and listing icon. Repository marketplace installation is not an official directory listing.

## Browser validation

Browser plugin was not available. Local Chromium could not start under the executor restrictions, and the alternative browser download failed. The committed Playwright workflow therefore runs on GitHub Actions, with actual screenshots retained temporarily in the workflow artifact. See the [Test workflow](https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence/actions/workflows/test.yml) for the current commit's result.

Flow: connect with an ephemeral test token → upload synthetic music/photo → analyze → load waveform → prepare full original audio → play/pause/seek → add marker → verify unsaved-edit guard → undo → save an immutable marker copy → apply 120 BPM tempo map → prepare click audio → save project against the corrected analysis → render montage preview → play/pause/seek and inspect decoded media dimensions/duration → export JSON and check timing provenance → revise caption → disconnect and verify asset/marker/audio/video state clears. Mobile also loads the waveform, changes its view range and exercises marker add/reset.

Viewports: concept-native 1505×1045, desktop 1440×1000, mobile 390×844. The browser test checks identity, meaningful content, console/page errors, overflow, media readiness/playback and interaction results. No customer credentials or copyrighted tracks are used in screenshots.

## Visual fidelity ledger

| Area | Concept and implementation | Verification / intentional difference |
| --- | --- | --- |
| Copy | Same main heading, supporting sentence, media/edit/preview hierarchy and action labels | No invented hero badges, metrics, navigation or feature claims |
| Layout | Open two-column desktop workspace with editor and vertical preview; no nested card grid | Mobile becomes one column; primary actions stack to keep labels readable |
| Palette | True white, navy content, Fusionify blue controls and subtle borders | No decorative raster imagery or tinted page background |
| Typography | System sans, strong headline, compact labels and regular-weight field values | Native form controls vary with browser/platform |
| Media | Dark vertical placeholder becomes actual video after rendering | Aspect changes follow the user's output selection; preview is not a fake animation |
| States | Explicit upload, analysis, revision and render results | Controls require authentication; this is intentionally stricter than the visual concept's empty-state buttons |
| Duration | Full soundtrack is represented by an empty custom duration field | Number input allows an exact requested duration rather than a decorative dropdown |
| Render revision | Completed result identifies the rendered revision separately from current saved revision | Prevents a newly edited form from implying an old preview is current |
| Rhythm editing | Collapsible timing editor extends the same navy/blue form and waveform treatment | Original audio is explicitly prepared, playback is user-initiated, keyboard seek/marker controls accompany the canvas |

The established v0.2 desktop/mobile design was visually reviewed against the generated concept. v0.3 extends that layout with a collapsible rhythm editor. The successful initial v0.3 [CI run](https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence/actions/runs/41332303420) produced desktop/mobile screenshots which were visually inspected: waveform and marker lines are visible, timing controls fit their columns, mobile actions wrap without clipping and no horizontal overflow is reported. Material v0.2 repairs include regular field weight, mobile action-label clipping, real playback readiness, and clearing asset/preview data on disconnect.

The browser script is the repeatable verification source; inspect the matching commit's successful workflow before treating a proposed change as browser-verified. The local executor has no Playwright headless-shell installation, so browser checks run in CI. Live tap-button cadence across browsers and human-perceived beat alignment still need a listening session; the backend tap estimator is covered by jitter/outlier fixtures.

## Checks still requiring an actual deployment/account

- Public HTTPS reachability and live Claude web/Desktop/Code UI setup.
- Live Gemini account/model access, cost and qualitative audio interpretation. Provider tests are mocked.
- Official plugin directory publication after license/icon selection and provider review.
- Perceptual timing review of varied real music, especially variable tempo and syncopation.

The workspace is single-owner. These tests do not establish tenant isolation or OAuth support.
