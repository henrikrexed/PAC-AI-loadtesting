# think.py — per-step think-time sampling (pure Python; used by the generated
# locustfile + tests). `rand` in [0,1) is supplied by the caller (random.random()).
# Mirrors the k6 `thinkSeconds()` helper so both renderers sample think-time the
# same way. `empirical` is a Locust approximation (declared by supports(), G-E1):
# Locust `wait_time` has no native empirical-sample distribution, so we sample the
# pre-generated empirical list here in the task body.

import math


def think_seconds(spec, rand):
    if not spec or not spec.get("distribution"):
        return 0.0
    dist = spec["distribution"]
    if dist == "constant":
        return (spec.get("meanMs") or 0) / 1000.0
    if dist == "uniform":
        lo = spec.get("minMs") or 0
        hi = spec.get("maxMs", lo)
        return (lo + rand * (hi - lo)) / 1000.0
    if dist == "exponential":
        mean = spec.get("meanMs") or 0
        # inverse-CDF of exponential; guard rand=0 -> log(1)
        return (-math.log(1 - min(rand, 0.999999)) * mean) / 1000.0
    if dist == "empirical":
        samples = spec.get("samples") or []
        if not samples:
            return 0.0
        return samples[min(len(samples) - 1, int(rand * len(samples)))] / 1000.0
    return 0.0
