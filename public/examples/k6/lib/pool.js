// pool.js — runtime payload samplers (pure JS; used by generated k6 scripts + tests).
//
// Cache-key pools are sampled by inverse-transform over the Zipf CDF so the test
// reproduces production's key-reuse (and therefore its cache hit ratio, G4).
// Record pools are sampled uniformly.

/** Inverse-transform sample of a cache-key pool. `rand` in [0,1). */
export function pickKey(pool, rand) {
  const cdf = pool.cdf;
  let lo = 0;
  let hi = cdf.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (rand <= cdf[mid]) hi = mid;
    else lo = mid + 1;
  }
  return pool.keys[lo];
}

/** Uniform sample of a record pool. */
export function pickRecord(pool, rand) {
  const i = Math.min(pool.records.length - 1, Math.floor(rand * pool.records.length));
  return pool.records[i];
}
