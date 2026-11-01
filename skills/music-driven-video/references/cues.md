# Lock a story cue and review the right part

## Two clocks

Distinguish the full saved project from the full source file. Read the source duration and selected music range before calling a final output full-song. Reviewing an excerpt must not change that range; if the user explicitly requests music through the source end, retain the existing start/cue locks and change duration deliberately rather than silently discarding the source tail.

- `source_time_s`: absolute seconds from the analyzed music file, before the project trim.
- `preview_start_s`: seconds from the start of the saved video project.
- Conversion: `project_time = source_time - music_in_s`.

If a project begins at source second 5 and a cue is at source second 17.425, the cue appears at project second 12.425. A preview starting 1.5 seconds before that cue uses `preview_start_s: 10.925`, not 15.925 or 17.425.

## Source-time anchors

`section_anchors` contains ordered `{section_index, source_time_s}` entries. Indices are zero-based: section 0 is the first story block and is implicitly fixed to `music_in_s`; section 2 is the third block. Anchors accept later section indices 1–7 within the actual planned section count. Times must be inside the selected music range, strictly ordered, and leave readable holds between locked boundaries.

For a five-block native story, a chosen third-message cue can be represented as:

```json
{
  "section_anchors": [
    {"section_index": 2, "source_time_s": 17.425}
  ]
}
```

Use the same anchors and matching `section_count` in `create_music_direction` when proposing timing. The chosen time is a user direction; the planner does not declare it an automatically detected drop or downbeat. Unlocked sections can move within the spans between anchors.

To revise only one cue while preserving other timing:

1. Read `get_video_project` and `get_project_timeline`, including `music_sections` and `section_anchors`.
2. Resolve the intended story block from its current index/copy. Keep other option fields and full duration.
3. Build anchors for every existing later section that must stay unchanged, then change only the requested cue. Do not assume unlocked boundaries will stay still after replanning.
4. Call `revise_video_project` with the current expected revision and the intended changes. Preserve story text/assets unless the user requested copy or material changes.
5. If rejected for insufficient reading time, explain the concrete conflicting span. Reduce text/blocks, choose another cue, or change pacing only within the user's preference. Do not silently move the surrounding locked sections to make validation pass.

Anchors require musical pacing (native motion graphics uses musical pacing automatically), and cannot coexist with `scene_overrides`. For exact footage placements using full explicit scenes, continue using `scene_overrides` instead of adding conflicting anchors. Too many selected montage assets for the anchored section count is rejected rather than redistributing and losing the locks. Remap indices deliberately if story blocks are reordered.

## Targeted review without changing the full project

```json
{
  "project_id": "ACTUAL_PROJECT_ID",
  "preview": true,
  "preview_start_s": 10.925,
  "preview_duration_s": 6
}
```

Call `render_video_project` with the range above only when it fits the current saved project. Preview length is at least one frame and at most eight seconds. The queue/status result identifies project, revision, preview start and duration. Poll to completion; present the actual artifact and explicitly call it a selected excerpt.

The excerpt retains its original story block, music source offset, project motion clock, preceding beat decay, footage clock and fixed per-scene effect progress. A frame-based output still has 30 fps quantization; do not promise sub-frame visual precision. Previewing does not revise the project or make an incomplete excerpt a full-song deliverable.

Inspect a lead-in and the target transition, then the closing when relevant. For final delivery call `render_video_project` with `preview: false` and omit both preview-range fields. Never revise music_in_s/duration_s to create a quick review sample; those fields change the actual saved edit.
