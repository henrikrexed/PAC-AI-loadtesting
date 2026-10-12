"""Arrival-rate, concurrency and ramp shaping for the SCOPE stage (§3.1 step 5, gate G3).

All pure functions. The caller extracts the raw telemetry (per-minute arrival curve via
G3-B, server-side response time via the server-span query, entry counts via G3-A) and
feeds it here. The three jobs:

  * pace()            — per-scenario arrival rate (TPS/TPM) from entry counts / window.
  * littles_law()     — concurrency sanity check, MUST use the SERVER span response time,
                        never the load-driver wrapper (the wrapper bakes in think-time and
                        inflates concurrency by orders of magnitude — a repeatedly
                        observed finding).
  * shape_ramp()      — CoV gate: steady (<0.15) -> one constant stage; else piecewise-
                        linear segmentation of the per-minute curve to <=6 ramp stages
                        with a mandatory ramp-down tail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

COV_STEADY_MAX = 0.15
MAX_RAMP_STAGES = 6
LITTLES_LAW_RATIO_BAND = (0.5, 2.0)


@dataclass
class Pace:
    tps: float
    tpm: float


def pace(entry_count: int, window_seconds: float, *, sampling_ratio: float = 1.0) -> Pace:
    """Arrival rate from entry-trace count / window.

    `sampling_ratio` < 1.0 scales counts up (R1): if the tenant sampled at 5%, pass 0.05
    and the observed count is divided by it before the rate is computed.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if not (0 < sampling_ratio <= 1.0):
        raise ValueError("sampling_ratio must be in (0, 1]")
    corrected = entry_count / sampling_ratio
    return Pace(tps=corrected / window_seconds, tpm=corrected / (window_seconds / 60.0))


@dataclass
class LittlesLaw:
    expectedConcurrency: float
    observedConcurrency: float
    ratio: float

    @property
    def passes(self) -> bool:
        lo, hi = LITTLES_LAW_RATIO_BAND
        return lo <= self.ratio <= hi


def littles_law(
    arrival_rate_tps: float,
    mean_server_response_ms: float,
    observed_concurrency: float,
) -> LittlesLaw:
    """L = lambda * W. `mean_server_response_ms` MUST come from the server-side entry span.

    `observed_concurrency` is an independently derived occupancy estimate — e.g. the
    busy-time integral sum(span.duration)/window over the same server-span population.
    The ratio expected/observed must land in [0.5, 2.0] for G0 to pass.
    """
    expected = arrival_rate_tps * (mean_server_response_ms / 1000.0)
    ratio = (expected / observed_concurrency) if observed_concurrency else float("inf")
    return LittlesLaw(round(expected, 4), round(observed_concurrency, 4), round(ratio, 4))


def think_time_ms(wrapper_duration_ms: float, server_response_ms: float) -> float:
    """Recover per-journey think-time: wrapper - server response (§3.1 step 3)."""
    return max(0.0, wrapper_duration_ms - server_response_ms)


def trim_partial_bins(per_minute_counts: list[float], *, frac: float = 0.5) -> list[float]:
    """Drop leading/trailing partial-window bins before CoV/ramp analysis.

    Absolute-timestamp binning (Grail `bin(start_time, 1m)`) almost always yields a partial
    first and last bucket — the window rarely starts/ends on a minute boundary. Those low
    edge counts inflate stddev and can falsely trip the CoV ramp gate on otherwise-steady
    traffic (observed live on crewai-deepseek-agent: full-window CoV 0.166 vs interior 0.016).
    Drop an edge bin when it is below `frac` x the median of the interior.
    """
    if len(per_minute_counts) <= 2:
        return list(per_minute_counts)
    interior = sorted(per_minute_counts[1:-1])
    med = interior[len(interior) // 2] if interior else 0.0
    out = list(per_minute_counts)
    if med and out[0] < frac * med:
        out = out[1:]
    if med and out and out[-1] < frac * med:
        out = out[:-1]
    return out


def coefficient_of_variation(per_minute_counts: list[float], *, trim: bool = True) -> float:
    """CoV = stddev / mean of the per-minute arrival curve (partial edge bins trimmed)."""
    counts = trim_partial_bins(per_minute_counts) if trim else per_minute_counts
    n = len(counts)
    if n == 0:
        return 0.0
    mean = sum(counts) / n
    if mean == 0:
        return 0.0
    var = sum((c - mean) ** 2 for c in counts) / n
    return math.sqrt(var) / mean


@dataclass
class Stage:
    duration: str
    rate: float
    shape: str  # steady | ramp_up | plateau | ramp_down


def _fmt_minutes(n: int) -> str:
    return f"{max(1, n)}m"


def shape_ramp(
    per_minute_counts: list[float],
    *,
    cov_steady_max: float = COV_STEADY_MAX,
    max_stages: int = MAX_RAMP_STAGES,
    rampdown_minutes: int = 2,
) -> tuple[list[Stage], float]:
    """Turn a per-minute arrival curve into <=6 arrival stages. Returns (stages, cov).

    CoV < threshold  -> one steady constant-arrival-rate stage + a mandatory short
                        ramp-down tail (graceful stop; §6 / §3.3 rule 2).
    CoV >= threshold -> locate the global-peak minute, split into monotone ramp-up prefix,
                        plateau, monotone ramp-down suffix, and piecewise-linear-segment to
                        <=max_stages stages (rate = segment mean, duration = segment length).
                        The ramp-down tail is always present.
    Rates are per-second (counts are per-minute -> divide by 60).
    """
    per_minute_counts = trim_partial_bins(per_minute_counts)
    cov = coefficient_of_variation(per_minute_counts, trim=False)
    n = len(per_minute_counts)
    if n == 0:
        return [], 0.0
    mean_rpm = sum(per_minute_counts) / n
    mean_rps = mean_rpm / 60.0

    if cov < cov_steady_max:
        body = max(1, n - rampdown_minutes)
        return (
            [
                Stage(_fmt_minutes(body), round(mean_rps, 4), "steady"),
                Stage(_fmt_minutes(rampdown_minutes), 0.0, "ramp_down"),
            ],
            cov,
        )

    # --- ramp case: split around the global peak ---
    peak_idx = max(range(n), key=lambda i: per_minute_counts[i])
    rise = per_minute_counts[: peak_idx + 1]
    fall = per_minute_counts[peak_idx:]

    segments: list[tuple[list[float], str]] = []
    if len(rise) > 1:
        segments.append((rise, "ramp_up"))
    segments.append(([per_minute_counts[peak_idx]], "plateau"))
    if len(fall) > 1:
        segments.append((fall[1:], "ramp_down"))

    # merge/limit to max_stages by greedily combining the smallest adjacent same-shape runs
    stages = [
        Stage(_fmt_minutes(len(seg)), round((sum(seg) / len(seg)) / 60.0, 4), shape)
        for seg, shape in segments
        if seg
    ]
    stages = _limit_stages(stages, max_stages)

    # guarantee a ramp-down tail exists
    if not any(s.shape == "ramp_down" for s in stages):
        stages.append(Stage(_fmt_minutes(rampdown_minutes), 0.0, "ramp_down"))
    return stages, cov


def _limit_stages(stages: list[Stage], max_stages: int) -> list[Stage]:
    """Collapse the lowest-impact adjacent stages until len <= max_stages."""
    while len(stages) > max_stages:
        # find adjacent pair with closest rates and merge (duration-weighted mean rate)
        best_i, best_gap = 0, float("inf")
        for i in range(len(stages) - 1):
            gap = abs(stages[i].rate - stages[i + 1].rate)
            if gap < best_gap:
                best_gap, best_i = gap, i
        a, b = stages[best_i], stages[best_i + 1]
        da, db = int(a.duration[:-1]), int(b.duration[:-1])
        merged_rate = (a.rate * da + b.rate * db) / (da + db) if (da + db) else a.rate
        shape = a.shape if a.shape == b.shape else "plateau"
        stages[best_i : best_i + 2] = [Stage(_fmt_minutes(da + db), round(merged_rate, 4), shape)]
    return stages
