// feeders.mjs — payload pools -> Gatling JSON feeders (G4 cache-avoidance).
//
// Reuses the VALIDATED Zipf-pool math from k6-synthesis (`generatePool`) so the
// Gatling feeder reproduces the SAME production popularity skew / cache hit ratio
// as the k6 renderer — no second implementation to drift. The one Gatling-specific
// step: Gatling's `jsonFile(...).random` samples a flat record array UNIFORMLY, so
// to reproduce a Zipf hit ratio we materialize a Zipf-distributed MULTISET (an
// inverse-transform realization over the pool CDF), then `.random` over it yields
// the intended skew. Deterministic for a given seed.

import { generatePool, mulberry32 } from '../../k6-synthesis/lib/payloads.mjs';
import { durationToSeconds } from './injection.mjs';

const FEEDER_SAMPLE_SIZE = 1000;

/** Sizing context for a cache pool: combined arrival share of journeys using it. */
export function poolContext(model, poolId) {
  const spec = model.spec;
  const peakRate = (spec.arrivalProfile.stages || []).reduce((m, s) => Math.max(m, Number(s.rate) || 0), 0);
  const durationSec = (spec.arrivalProfile.stages || []).reduce((sum, s) => sum + durationToSeconds(s.duration), 0);
  let share = 0;
  for (const j of spec.journeys || []) {
    if ((j.steps || []).some((s) => s.payloadRef === poolId)) share += j.weight || 0;
  }
  share = Math.min(1, share);
  return { ratePerSec: Math.max(1, peakRate * share), ttlSec: 60, durationSec: Math.max(1, durationSec) };
}

/** Inverse-transform Zipf sample over a CDF — deterministic given the seed. */
function zipfSample(keys, cdf, n, seed) {
  const rng = mulberry32(((seed >>> 0) ^ 0x9e3779b9) >>> 0);
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    const r = rng();
    let lo = 0;
    let hi = cdf.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (r <= cdf[mid]) hi = mid;
      else lo = mid + 1;
    }
    out[i] = keys[lo];
  }
  return out;
}

/**
 * Build a Gatling feeder for one pool.
 * Returns { id, kind, fields:[name], records:[{field:value}], cacheProfile? }.
 */
export function buildFeeder(model, poolId) {
  const poolSpec = (model.spec.payloads || {})[poolId];
  if (!poolSpec) throw new Error(`no payload pool "${poolId}"`);
  const pool = generatePool(poolId, poolSpec, poolContext(model, poolId));
  const f0 = poolSpec.fields && poolSpec.fields[0];

  if (pool.kind === 'cache-key') {
    const keyField = (f0 && f0.name) || 'id';
    let keys = pool.keys;
    // honor an explicit enum value-set as the real key universe when it lines up
    // with the fitted cardinality (e.g. the 10 real otel-demo product ids).
    if (f0 && f0.type === 'enum' && Array.isArray(f0.values) && f0.values.length === keys.length) {
      keys = f0.values.slice();
    }
    const records = zipfSample(keys, pool.cdf, FEEDER_SAMPLE_SIZE, poolSpec.seed ?? 1).map((k) => ({ [keyField]: k }));
    return { id: poolId, kind: 'cache-key', fields: [keyField], records, cacheProfile: pool.cacheProfile };
  }
  // record pool: PII-free generated records used directly as the feeder array.
  return {
    id: poolId,
    kind: 'record',
    fields: (poolSpec.fields || []).map((f) => f.name),
    records: pool.records,
  };
}
