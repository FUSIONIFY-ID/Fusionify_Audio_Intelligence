"""Explicit timing directions, distinct from measured audio onsets."""
from __future__ import annotations

import math
from typing import Annotated

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

Number = Annotated[StrictFloat | StrictInt, Field(allow_inf_nan=False)]


class TempoRegion(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    start_s: Number = Field(ge=0)
    end_s: Number = Field(gt=0)
    bpm: Number = Field(ge=30, le=300)
    first_beat_s: Number = Field(ge=0)


def estimate_taps(tap_times_s: list[float]) -> dict:
    """Robust consecutive-interval estimate; taps are not independent beat truth."""
    if not isinstance(tap_times_s, list) or not 4 <= len(tap_times_s) <= 128:
        raise ValueError('Supply 4 to 128 ordered tap times in seconds.')
    if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t)
           or not 0 <= t <= 180 for t in tap_times_s):
        raise ValueError('Tap times must be finite source-relative seconds from 0 to 180.')
    intervals = np.diff(tap_times_s)
    if np.any(intervals <= 0):
        raise ValueError('Tap times must be unique and strictly increasing.')
    median = float(np.median(intervals))
    # Ignore isolated missed/extra taps. A low accepted fraction is a retry, not a BPM guess.
    accepted = intervals[np.abs(intervals - median) <= .2 * median]
    if len(accepted) < 3 or len(accepted) / len(intervals) < .6:
        raise ValueError('Taps are too inconsistent. Tap at least four evenly spaced pulses again.')
    period = float(np.median(accepted))
    bpm = 60 / period
    if not 30 <= bpm <= 300:
        raise ValueError('Tap tempo must be between 30 and 300 BPM.')
    return {'tempo_bpm_estimate': round(bpm, 4), 'first_tap_s': tap_times_s[0],
            'accepted_intervals': len(accepted), 'discarded_intervals': len(intervals) - len(accepted),
            'median_interval_s': round(period, 6),
            'interval_jitter_ratio': round(float(np.median(np.abs(accepted - period))) / period, 4),
            'provenance': 'user taps; not independently verified',
            'note': 'Tap consistency is not musical accuracy. Half/double-time interpretation still needs listening.'}


def tempo_map_beats(report: dict, regions: list[dict], snap_tolerance_s: float = 0) -> tuple[list[dict], list[dict]]:
    if not isinstance(regions, list) or not 1 <= len(regions) <= 32:
        raise ValueError('Supply 1 to 32 ordered tempo regions.')
    if isinstance(snap_tolerance_s, bool) or not isinstance(snap_tolerance_s, (int, float)) \
            or not math.isfinite(snap_tolerance_s) or not 0 <= snap_tolerance_s <= .1:
        raise ValueError('Snap tolerance must be a finite number from 0 to 0.1 seconds.')
    parsed = [TempoRegion.model_validate(r).model_dump() for r in regions]
    previous_end = 0
    beats = []
    onsets = report.get('onsets', [])
    for region in parsed:
        start, end, first, bpm = (region[k] for k in ('start_s', 'end_s', 'first_beat_s', 'bpm'))
        if start < previous_end or end <= start or end > report['duration_s']:
            raise ValueError('Tempo regions must be ordered, non-overlapping and inside the source duration.')
        if not start <= first < end:
            raise ValueError('First beat must be inside its own tempo region.')
        previous_end = end
        period = 60 / bpm
        count = math.ceil((end - first) / period)
        available = [o for o in onsets if start <= o['time_s'] < end]
        for i in range(count):
            grid = round(first + i * period, 6)
            if grid >= end:
                continue
            marker = {'time_s': grid, 'strength': 1, 'provenance': 'user_tempo_grid', 'grid_time_s': grid}
            # Less than half a period prevents adjacent grid beats snapping to the same onset.
            tolerance = min(snap_tolerance_s, .45 * period)
            nearby = [o for o in available if abs(o['time_s'] - grid) <= tolerance]
            if tolerance and nearby:
                onset = min(nearby, key=lambda o: (abs(o['time_s'] - grid), -o['strength']))
                marker.update(time_s=onset['time_s'], strength=onset['strength'], provenance='user_grid_snapped_to_measured_onset')
            if beats and marker['time_s'] <= beats[-1]['time_s']:
                raise ValueError('Tempo map creates duplicate or reversed markers. Adjust region boundaries.')
            beats.append(marker)
    return beats, parsed
