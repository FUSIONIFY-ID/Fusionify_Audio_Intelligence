# Verification notes for v0.2

## Backend and protocol checks

The automated suite covers 19 tests for synthetic pulses and silence, decode boundaries, path/symlink restrictions, malformed authorization, signed download expiry/tampering, upload validation, revisions, persistence, cancellation, manual markers, explicit scenes, config merging, montage render/audio offsets and mocked provider contracts. Separate smoke scripts exercise actual MCP initialization/discovery/calls over both stdio and TCP Streamable HTTP.

Waveform/MP3 and image/video montage outputs are decoded and probed, including short video looping and music in-points. Audio correlation checks use a known synthetic source; they do not establish perceptual alignment for every musical style. A package build also verifies the HTML/CSS/JS console is included in the wheel.

The Claude CLI manifest validator is run with `--strict`. Its plugin-directory profile is a different check: official directory submission still needs an owner-selected license and listing icon. Repository marketplace installation is not an official directory listing.

## Browser validation

Browser plugin was not available. Local Chromium could not start under the executor restrictions, and the alternative browser download failed. The committed Playwright workflow therefore runs on GitHub Actions, with actual screenshots retained temporarily in the workflow artifact. See the [Test workflow](https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence/actions/workflows/test.yml) for the current commit's result.

Flow: connect with an ephemeral test token → upload synthetic music/photo → analyze actual audio → save project → render montage preview → play/pause/seek and inspect decoded media dimensions/duration → export JSON → revise caption → disconnect and verify sensitive page state clears.

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

Desktop/mobile screenshots are visually reviewed against the generated concept. The UI preserves the concept's hierarchy, palette, open layout, typography roles and media treatment. Material repairs include regular field weight, mobile action-label clipping, real playback readiness, and clearing asset/preview data on disconnect.

## Checks still requiring an actual deployment/account

- Public HTTPS reachability and live Claude web/Desktop/Code UI setup.
- Live Gemini account/model access, cost and qualitative audio interpretation. Provider tests are mocked.
- Official plugin directory publication after license/icon selection and provider review.
- Perceptual timing review of varied real music, especially variable tempo and syncopation.

The workspace is single-owner. These tests do not establish tenant isolation or OAuth support.
