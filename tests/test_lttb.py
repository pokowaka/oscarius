"""Tests for the Largest-Triangle-Three-Buckets (LTTB) signal downsampling algorithm."""

import pytest
import numpy as np

from oscarius.signal.lttb import lttb_downsample, window_and_downsample


def test_lttb_returns_original_when_below_threshold():
    times = [100, 200, 300, 400]
    vals = [1.0, 2.0, 3.0, 4.0]
    out_t, out_v = lttb_downsample(times, vals, threshold=10)
    assert out_t == times
    assert out_v == vals


def test_lttb_preserves_first_and_last_points():
    n = 1000
    times = list(range(n))
    vals = [float(x) for x in range(n)]
    
    out_t, out_v = lttb_downsample(times, vals, threshold=50)
    assert len(out_t) == 50
    assert len(out_v) == 50
    assert out_t[0] == times[0]
    assert out_v[0] == vals[0]
    assert out_t[-1] == times[-1]
    assert out_v[-1] == vals[-1]


def test_lttb_preserves_peaks_and_valleys():
    # A flat baseline with a sharp peak in the middle
    n = 100
    times = list(range(n))
    vals = [0.0] * n
    vals[50] = 100.0  # Sharp spike
    
    out_t, out_v = lttb_downsample(times, vals, threshold=10)
    assert len(out_t) == 10
    # The peak at index 50 must be preserved in the downsampled output
    assert 100.0 in out_v
    assert 50 in out_t


def test_window_and_downsample_slices_range():
    # 1000 points from t=0 to t=999
    times = list(range(1000))
    vals = [float(x) for x in range(1000)]
    
    # Slice only t=200 to t=400
    out_t, out_v = window_and_downsample(
        times, vals, target_points=20, start_time_ms=200, end_time_ms=400
    )
    assert len(out_t) == 20
    assert min(out_t) >= 200
    assert max(out_t) <= 400
