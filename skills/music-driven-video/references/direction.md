# Match music to the content

## Separate evidence from creative decisions

Use duration, source-relative timing, energy measurements, candidate onsets and user corrections as evidence. The host assistant chooses what the video communicates. `content_brief` is recorded with the plan; the DSP algorithm does not understand a business, product, lyrics or narrative from that brief. Optional provider interpretation is separate and requires explicit external-processing agreement.

`create_music_direction` proposes readable sections. It prefers eligible measured energy rises, then nearby pulse/user markers, otherwise explicit editorial spacing. The roles opening/development/feature/closing are suggested storytelling positions. They are never verified intro, chorus or drop labels. `accent_count` counts small pulse reactions, not the number of requested scene cuts. Use two levels of direction:

- **Major changes:** a new message, meaningful visual composition, asset change or sustained chapter emphasis.
- **Micro reactions:** restrained scale, rotation, spectrum or waveform movement while a message remains readable. A beat does not require a cut.

Keep content seriousness and reading time ahead of raw track energy. A busy breakbeat can accompany a calm brand story with low `motion_amount`; fast music does not establish permission for shaking logos or rapidly replacing text. Silence has no invented beat accents. Continuous editorial motion can still be used and described as such.

## Choose a visual route

| Available material and intent | Direction |
| --- | --- |
| Product/brand story with limited assets | Native motion graphics, musical pacing, user-approved messages from hook to closing; four or five concise blocks normally suffice |
| Creator JJ or deliberate rhythmic collage | Select actual images/clips, choose pulse-cut or musical pacing explicitly, keep only requested motion intensity |
| Cinematic or explanation | Musical pacing, longer readable holds and low motion; reduce copy before forcing more fast sections |
| Finished designed footage already matched to the same soundtrack | Preserve composition, turn text_overlay off, use source_sync or explicit video in-points rather than slowing its original visual progression between stills |
| Raw footage | Montage with selected assets, one intentional title/caption layer where needed; inspect for existing copy before enabling it |

Native `story_blocks` are declarative data:

Native graphics implement pulse micro reactions while holding their story section. Montage musical pacing changes major scene timing; footage still uses its fixed cut/zoom/pan/shake preset per scene, and does not synthesize an extra reaction on every beat.

```json
{
  "visual_mode": "motion_graphics",
  "pacing_mode": "musical",
  "brand": "USER BRAND",
  "accent_color": "lime",
  "content_brief": "Introduce the product and close with its name; original soundtrack throughout.",
  "story_blocks": [
    {"headline": "YOUR OPENING MESSAGE", "support": "A short, supplied or clearly creative line.", "visual": "globe"},
    {"headline": "ONE CLEAR IDEA", "support": "Keep it readable while the music moves.", "visual": "orbit"},
    {"headline": "YOUR CLOSING MESSAGE", "support": "Use the actual brand or requested action.", "visual": "spectrum"}
  ]
}
```

Use up to eight blocks. Short source ranges may not support every block at the current intensity; reduce copy/blocks or use a longer range before making pacing faster. No visual assets or scene overrides accompany native blocks. The default native renderer uses its own title/support layout, so it never adds a montage title over it. Globe rotation uses one continuous project clock. A native market visual is an audio-amplitude illustration, explicitly labeled; it is not real transactions, a geographic map, conversion analytics or a stock price. Do not attach unverified business numbers to it.

## Review before delivery

Call `review_content_fit` after saving and after changes. Fix relevant flags; a flag can be an inspection request rather than a demonstrated defect. It does not see pixels or judge semantic content. Then inspect an actual preview with available tools:

1. Check the opening and one boundary frame. Does a visual clock jump back or does movement continue?
2. Check every story block for readable hierarchy, fitting text, repeated titles and room for the main subject.
3. Compare video source offsets to soundtrack offsets, particularly when a composed clip is mixed with stills. Short clips can still loop; source_sync does not manufacture missing footage.
4. Use original/click audio for timing review. Do not call markers correct solely because a render job or audio-correlation test passed.
5. Keep the user's preferred earlier style when revising quality. Explain exactly what changed rather than promising a subjective improvement as verified fact.

Render the approved saved project at full duration. A preview is a prefix of its saved sequence, not a fresh shorter arrangement. Preserve the original and prior project IDs for comparison.
