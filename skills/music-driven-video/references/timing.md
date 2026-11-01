# Timing contract

- All analysis markers use seconds from the start of the exact decoded input.
- `video_time_s = source_time_s - music_in_s` for events inside the requested range.
- Keep fractional timestamps until converting to the target frame rate. A frame-based render introduces quantization; do not promise sub-frame visual precision.
- The global tempo is an editing pulse estimate. Half/double-time readings can both be plausible. The periodicity score is not accuracy or confidence calibrated against ground truth.
- Beat candidates are onsets close to a repeating pulse. They do not identify bar starts or downbeats.
- `energy_rise_candidate` marks a measured rise, not a confirmed chorus, drop, or build-up.
- Silence and ambiguous music can return `tempo_bpm_estimate: null` and no beat events. Do not fill missing data with invented markers.
- Changed source bytes require reanalysis. Rendering checks source SHA-256 against the stored analysis.
- Automatic tracking still estimates a global pulse. v0.3 tempo maps support explicit user-directed tempo regions; they do not automatically establish changing musical tempo.
- Musical pacing separates held editorial sections from small pulse reactions. Energy matches and pulse markers remain candidates; opening/feature/closing are creative roles.
- A preview uses the beginning of the saved full sequence rather than replanning the same story over a shorter duration.
- Test a selected region audibly and visually. A good numerical fit on detected onsets alone does not prove perceptual synchronization.
