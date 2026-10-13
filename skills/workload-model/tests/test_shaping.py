"""Arrival / concurrency / ramp shaping (G3) tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import shaping as sh  # noqa: E402


def test_pace_from_counts():
    p = sh.pace(7996, 10800)
    assert abs(p.tps - 0.7404) < 1e-3
    assert abs(p.tpm - 44.42) < 0.1


def test_pace_sampling_correction():
    # 5% sampling -> counts scaled up 20x
    full = sh.pace(100, 100, sampling_ratio=1.0).tps
    sampled = sh.pace(100, 100, sampling_ratio=0.05).tps
    assert abs(sampled - full * 20) < 1e-6


def test_littles_law_uses_server_time_and_passes_band():
    # example numbers: lambda=1.836/s, W=2018ms, observed 3.7
    llc = sh.littles_law(1.836, 2018, 3.7)
    assert 0.5 <= llc.ratio <= 2.0
    assert llc.passes


def test_littles_law_driver_wrapper_would_fail_sanity():
    # feeding the 15s load-driver wrapper instead of the 2s server mean inflates expected
    bad = sh.littles_law(1.836, 15002, 3.7)
    assert not bad.passes  # ratio ~7.4 -> caught


def test_think_time_recovered_from_wrapper_minus_server():
    assert sh.think_time_ms(15002, 3) == 14999
    assert sh.think_time_ms(3, 7) == 0.0  # never negative


def test_cov_flat_curve_is_steady():
    curve = [44.0] * 180
    stages, cov = sh.shape_ramp(curve)
    assert cov < sh.COV_STEADY_MAX
    assert stages[0].shape == "steady"
    assert stages[-1].shape == "ramp_down"  # mandatory tail


def test_cov_gate_threshold():
    assert sh.coefficient_of_variation([44.0] * 100) == 0.0
    assert sh.coefficient_of_variation([]) == 0.0


def test_ramp_curve_segments_and_bounds_stages():
    # triangular diurnal curve -> ramp_up + plateau + ramp_down, <=6 stages
    rise = list(range(1, 60))
    fall = list(range(59, 0, -1))
    curve = [float(x) for x in rise + [60.0] * 10 + fall]
    stages, cov = sh.shape_ramp(curve)
    assert cov >= sh.COV_STEADY_MAX
    assert len(stages) <= sh.MAX_RAMP_STAGES
    shapes = {s.shape for s in stages}
    assert "ramp_up" in shapes
    assert "ramp_down" in shapes  # ramp-down tail present


def test_partial_boundary_bins_do_not_false_trigger_ramp():
    # crewai-deepseek-agent live case: steady 12rpm k6 driver with partial first/last bins.
    # Raw CoV trips the ramp gate; trimmed CoV is steady.
    curve = [2.0] + [12.0] * 24 + [2.0]
    assert sh.coefficient_of_variation(curve, trim=False) >= sh.COV_STEADY_MAX  # raw would ramp
    assert sh.coefficient_of_variation(curve) < sh.COV_STEADY_MAX               # trimmed -> steady
    stages, cov = sh.shape_ramp(curve)
    assert stages[0].shape == "steady"
    assert cov < sh.COV_STEADY_MAX


def test_trim_keeps_genuine_ramp():
    # a real monotone ramp must NOT be flattened by trimming (edges are not partial here)
    curve = [float(x) for x in range(5, 60)] + [60.0] * 5 + [float(x) for x in range(55, 5, -1)]
    trimmed = sh.trim_partial_bins(curve)
    assert len(trimmed) >= len(curve) - 2
    assert sh.coefficient_of_variation(curve) >= sh.COV_STEADY_MAX  # still a ramp


def test_rates_are_per_second():
    curve = [60.0] * 60  # 60 per minute -> 1.0 per second
    stages, _ = sh.shape_ramp(curve)
    assert abs(stages[0].rate - 1.0) < 1e-6
