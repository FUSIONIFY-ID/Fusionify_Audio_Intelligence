# Verification notes for v0.5

## Locked cues and targeted review

v0.5 adds seven tests (37 total); the MCP tool count remains 29. Coverage includes source-relative anchors after a music trim, ordered/readable constraints and incompatible modes, preserving locked boundaries after ordinary project revision, and validating that preview parameters cannot silently shorten a final render.

Targeted native frames are compared directly against the corresponding full-timeline frames, including story block, header, original project clock, waveform, beat-decay strength and graphic position. A real native excerpt is encoded and its audio is correlated against the correct original source region. Two colored-footage checks establish that continue and source_sync modes use their distinct expected source offsets after intervening images. A real zooming-grid render compares the excerpt against the corresponding full-render image, checking that zoom progress does not restart.

Stdio and TCP HTTP MCP smoke scripts exercise source-time anchors and targeted native previews, including queued/completed project revision/range metadata and signed hosted output links. Existing opening-preview/browser behavior remains a regression check. Offline tests do not claim live Claude application UI compatibility or perceptual sync accuracy.

## Music-to-content direction

v0.4 adds five backend tests (30 total), two MCP tools (29 total), a source-evidence/editorial direction planner, native procedural graphics and content-fit checks. Added tests cover readable sections versus many micro accents, source offsets, eligible energy-rise preference, silence, continuous clocks across scene boundaries, bounded text in 9:16/16:9/1:1, actual native encoding and audio correlation, preview prefix preservation and source-synchronized clip playback without an overlay. A regression case reproduces rapid cuts, possible duplicate titles, mixed-media clock drift and short-clip loops; after the relevant option fixes, only the genuine short-source risk remains.

The native renderer is fixed application code. It does not run model-generated code. Its market visual is an explicitly labeled audio-derived illustration, not sales, geographic or financial data. The host assistant chooses story meaning from the user brief. Structural checks and numerical timing/audio tests do not establish subjective content quality or perceptual beat correctness.

Advanced v0.4 direction is currently through MCP/CLI. Existing console controls are kept compatible and the browser workflow remains a regression check; no new UI controls are claimed. The full-length demonstration is rendered through Service.create_project/render_project using the user's actual sound rather than an independent renderer outside the package.

## Backend and protocol checks

The automated suite covers 37 tests for synthetic pulses and silence, decode boundaries, path/symlink restrictions, malformed authorization, signed download expiry/tampering, upload validation, revisions, persistence, cancellation, manual markers, explicit scenes, config merging, montage render/audio offsets and mocked provider contracts. New rhythm coverage includes ordered tempo regions, exclusive boundaries/gaps, strict numeric inputs, nearby-onset snapping, tap jitter/outliers, immutable analysis lineage, complete waveform bins, project marker provenance and original/click preview duration/audio level. Separate smoke scripts exercise actual MCP initialization/discovery/calls over both stdio and TCP Streamable HTTP, including the three new rhythm tools (29 tools total).

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
