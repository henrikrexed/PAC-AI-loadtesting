# pool.py — runtime payload-pool / feeder samplers (pure Python; used by the
# generated locustfile + tests). The feeder files are the SAME pre-generated pool
# JSON the k6 renderer emits (G4 cache-avoidance): a cache-key pool carries a Zipf
# `keys` list + cumulative `cdf`, sampled here by inverse-transform so Locust
# reproduces production's key-reuse (and therefore its cache hit ratio). Record
# pools are sampled uniformly. `rand` in [0,1) is supplied by the caller.

import json


def load_feeder(path):
    with open(path, "r") as fh:
        return json.load(fh)


def pick_key(pool, rand):
    """Inverse-transform sample of a cache-key pool's Zipf CDF."""
    cdf = pool["cdf"]
    lo, hi = 0, len(cdf) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if rand <= cdf[mid]:
            hi = mid
        else:
            lo = mid + 1
    return pool["keys"][lo]


def pick_record(pool, rand):
    """Uniform sample of a record pool."""
    records = pool["records"]
    i = min(len(records) - 1, int(rand * len(records)))
    return records[i]
