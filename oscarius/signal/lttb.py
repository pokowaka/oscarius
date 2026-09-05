"""Largest-Triangle-Three-Buckets (LTTB) downsampling algorithm for time series.

Provides visual-feature-preserving signal decimation for high-frequency waveforms
(such as 25 Hz CPAP flow rates) to ensure smooth 60 fps rendering on web canvases.
"""

from typing import Optional, Sequence
import numpy as np


def lttb_downsample(
    timestamps: Sequence[int | float],
    values: Sequence[float],
    threshold: int,
) -> tuple[list[int | float], list[float]]:
    """Downsamples a time-series dataset to a target threshold using the LTTB algorithm.

    Preserves peaks, valleys, and waveform morphology without statistical flatlining.

    @param timestamps: Monotonically increasing time values (e.g. milliseconds).
    @param values: Corresponding signal amplitudes.
    @param threshold: Maximum target point count.
    @return: Tuple of (downsampled_timestamps, downsampled_values).
    """
    n_points = len(timestamps)
    if threshold >= n_points or threshold < 3:
        return list(timestamps), list(values)

    times_arr = np.asarray(timestamps, dtype=np.float64)
    vals_arr = np.asarray(values, dtype=np.float64)

    sampled_indices = [0]
    bucket_size = (n_points - 2) / (threshold - 2)

    a_idx = 0

    for i in range(threshold - 2):
        # Calculate point average for next bucket (bucket c)
        avg_start = int(np.floor((i + 1) * bucket_size)) + 1
        avg_end = min(int(np.floor((i + 2) * bucket_size)) + 1, n_points)

        avg_x = np.mean(times_arr[avg_start:avg_end])
        avg_y = np.mean(vals_arr[avg_start:avg_end])

        # Current bucket range (bucket b)
        curr_start = int(np.floor(i * bucket_size)) + 1
        curr_end = min(int(np.floor((i + 1) * bucket_size)) + 1, n_points)

        prev_x = times_arr[a_idx]
        prev_y = vals_arr[a_idx]

        # Find point in current bucket maximizing triangular area
        b_x = times_arr[curr_start:curr_end]
        b_y = vals_arr[curr_start:curr_end]

        areas = 0.5 * np.abs(
            (prev_x - avg_x) * (b_y - prev_y) - (prev_x - b_x) * (avg_y - prev_y)
        )

        max_idx = curr_start + int(np.argmax(areas))
        sampled_indices.append(max_idx)
        a_idx = max_idx

    sampled_indices.append(n_points - 1)

    out_times = [timestamps[idx] for idx in sampled_indices]
    out_vals = [float(vals_arr[idx]) for idx in sampled_indices]
    return out_times, out_vals


def window_and_downsample(
    timestamps: Sequence[int | float],
    values: Sequence[float],
    target_points: int,
    start_time_ms: Optional[int] = None,
    end_time_ms: Optional[int] = None,
) -> tuple[list[int | float], list[float]]:
    """Crops a waveform to an optional time window, then downsamples using LTTB.

    @param timestamps: Monotonically increasing time values in ms.
    @param values: Signal values.
    @param target_points: Target resolution point count.
    @param start_time_ms: Optional lower time bound.
    @param end_time_ms: Optional upper time bound.
    @return: Tuple of (downsampled_timestamps, downsampled_values).
    """
    times_arr = np.asarray(timestamps)
    vals_arr = np.asarray(values)

    mask = np.ones(len(times_arr), dtype=bool)
    if start_time_ms is not None:
        mask &= times_arr >= start_time_ms
    if end_time_ms is not None:
        mask &= times_arr <= end_time_ms

    sub_times = times_arr[mask]
    sub_vals = vals_arr[mask]

    if len(sub_times) == 0:
        return [], []

    return lttb_downsample(sub_times.tolist(), sub_vals.tolist(), target_points)
