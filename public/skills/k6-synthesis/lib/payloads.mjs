// payloads.mjs — synthetic payload pools + cache-avoidance dataset strategy (G4, §3.3 rule 4).
//
// Two pool kinds:
//   * cache-key pool (poolSpec.cacheProfile present) — a Zipf-popularity key set
//     sized + shaped to REPRODUCE production's cache hit ratio, not eliminate it.
//   * record pool (no cacheProfile) — PII-free synthetic field records.
//
// Everything is deterministic given the pool `seed` (methodology P2).

/** mulberry32 — small deterministic PRNG. */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Normalized Zipf probabilities over ranks 1..K with exponent `alpha`. */
export function zipfWeights(K, alpha) {
  const w = new Array(K);
  let sum = 0;
  for (let k = 1; k <= K; k++) {
    const x = 1 / Math.pow(k, alpha);
    w[k - 1] = x;
    sum += x;
  }
  for (let i = 0; i < K; i++) w[i] /= sum;
  return w;
}

/**
 * Closed-form expected cache hit ratio for a TTL/working-set model:
 * a request is a hit iff its key was seen within the last `W` requests
 * (W = rate x TTL). Under an independent-reference model with per-key
 * probability p_k, P(seen in last W) = 1-(1-p_k)^W, so
 *   hitRatio = sum_k p_k * (1 - (1-p_k)^W).
 * Computed with log1p/expm1 for numerical stability at small p_k.
 */
export function expectedHitRatio(K, alpha, W) {
  const p = zipfWeights(K, alpha);
  let h = 0;
  for (let i = 0; i < K; i++) {
    const pk = p[i];
    const miss = Math.exp(W * Math.log1p(-pk)); // (1-pk)^W
    h += pk * (1 - miss);
  }
  return h;
}

/**
 * Fit the Zipf exponent alpha so the expected hit ratio matches `target`
 * for a given key cardinality K and window W. expectedHitRatio is monotone
 * increasing in alpha, so a bisection converges. Returns { alpha, achieved,
 * clamped } — clamped=true when target is outside the achievable band.
 */
export function fitAlpha(K, W, target, { lo = 0, hi = 6, iters = 60 } = {}) {
  const atLo = expectedHitRatio(K, lo, W);
  const atHi = expectedHitRatio(K, hi, W);
  if (target <= atLo) return { alpha: lo, achieved: atLo, clamped: target < atLo - 1e-9 };
  if (target >= atHi) return { alpha: hi, achieved: atHi, clamped: target > atHi + 1e-9 };
  let a = lo;
  let b = hi;
  for (let i = 0; i < iters; i++) {
    const mid = (a + b) / 2;
    const h = expectedHitRatio(K, mid, W);
    if (h < target) a = mid;
    else b = mid;
  }
  const alpha = (a + b) / 2;
  return { alpha, achieved: expectedHitRatio(K, alpha, W), clamped: false };
}

/**
 * Key-pool sizing math (§3.3 rule 4). `mode`:
 *   'ttl-miss'   K >= R*T*m_prod  (min to avoid forced all-hits in one TTL)
 *   'ttl-unique' K >= R*T         (no key reused within a TTL window)
 *   'run-unique' K >= R*D         (one-pass uniqueness across the whole run)
 */
export function sizePool({ R, T, D, missRatio, mode = 'ttl-miss' }) {
  switch (mode) {
    case 'ttl-unique':
      return Math.max(1, Math.ceil(R * T));
    case 'run-unique':
      return Math.max(1, Math.ceil(R * D));
    case 'ttl-miss':
    default:
      return Math.max(1, Math.ceil(R * T * (missRatio ?? 1)));
  }
}

/** Build a cumulative CDF (for inverse-transform sampling at k6 runtime). */
function cdfFromWeights(weights) {
  const cdf = new Array(weights.length);
  let acc = 0;
  for (let i = 0; i < weights.length; i++) {
    acc += weights[i];
    cdf[i] = acc;
  }
  cdf[cdf.length - 1] = 1; // guard against float drift
  return cdf;
}

/**
 * Monte-Carlo validation of the TTL/window hit model — used by tests to confirm
 * that actual Zipf draws reproduce the analytic target. Draws N keys by the
 * pool CDF and counts a hit when the key reappeared within the last W draws.
 * Warm-up (first W draws) is excluded so the ratio is steady-state.
 */
export function simulateHitRatio({ cdf, W, N, seed = 1 }) {
  const rng = mulberry32(seed);
  const lastSeen = new Map();
  let hits = 0;
  let counted = 0;
  for (let i = 0; i < N; i++) {
    const r = rng();
    // binary search the CDF
    let loI = 0;
    let hiI = cdf.length - 1;
    while (loI < hiI) {
      const mid = (loI + hiI) >> 1;
      if (r <= cdf[mid]) hiI = mid;
      else loI = mid + 1;
    }
    const key = loI;
    if (i >= W) {
      counted++;
      const seenAt = lastSeen.get(key);
      if (seenAt !== undefined && i - seenAt <= W) hits++;
    }
    lastSeen.set(key, i);
  }
  return counted > 0 ? hits / counted : 0;
}

const PII_SAFE_DOMAIN = 'synthetic.invalid';

/** Deterministic, PII-free field value generators. */
function genFieldValue(field, i, rng) {
  const g = field.generator || 'random';
  switch (field.type) {
    case 'int':
      return Math.floor(rng() * 1000);
    case 'float':
      return Math.round(rng() * 100000) / 100;
    case 'uuid':
      return uuidFrom(rng);
    case 'timestamp':
      return 0; // placeholder; runtime stamps real time to keep pool deterministic
    case 'enum': {
      const vals = field.values || [];
      if (vals.length === 0) return null;
      return vals[Math.floor(rng() * vals.length)];
    }
    case 'null':
      return null;
    case 'string':
    default:
      if (g === 'sequence') return `${field.name}-${String(i).padStart(5, '0')}`;
      if (g && g.startsWith('faker:email')) return `user${i}@${PII_SAFE_DOMAIN}`;
      if (g && g.startsWith('faker:')) return `${g.slice(6)}-${i}`;
      if (g === 'const') return (field.values && field.values[0]) ?? '';
      return `${field.name}-${Math.floor(rng() * 1e9).toString(36)}`;
  }
}

function uuidFrom(rng) {
  const hex = [];
  for (let i = 0; i < 16; i++) hex.push(Math.floor(rng() * 256));
  hex[6] = (hex[6] & 0x0f) | 0x40;
  hex[8] = (hex[8] & 0x3f) | 0x80;
  const s = hex.map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}

/**
 * Generate a payload pool for one poolSpec.
 * ctx = { ratePerSec, ttlSec, durationSec } used to size/shape cache pools.
 * Returns the JSON-serializable pool object written to payloads/<id>.json.
 */
export function generatePool(id, poolSpec, ctx = {}) {
  const seed = poolSpec.seed ?? 1;
  if (poolSpec.cacheProfile) {
    const cp = poolSpec.cacheProfile;
    const R = ctx.ratePerSec ?? 1;
    const T = ctx.ttlSec ?? 60;
    const D = ctx.durationSec ?? 600;
    const target = cp.targetHitRatio ?? 0;
    const missRatio = 1 - target;
    const K =
      cp.keyCardinality ??
      sizePool({ R, T, D, missRatio, mode: 'ttl-miss' });
    const W = Math.max(1, Math.round(R * T));
    // honor a pinned alpha; otherwise fit it to reproduce the target hit ratio
    let alpha;
    let achieved;
    let clamped = false;
    if (typeof cp.distributionAlpha === 'number') {
      alpha = cp.distributionAlpha;
      achieved = expectedHitRatio(K, alpha, W);
    } else {
      const fit = fitAlpha(K, W, target);
      alpha = fit.alpha;
      achieved = fit.achieved;
      clamped = fit.clamped;
    }
    const weights = zipfWeights(K, alpha);
    const cdf = cdfFromWeights(weights);
    const keyField = poolSpec.fields && poolSpec.fields[0] ? poolSpec.fields[0].name : 'id';
    const keys = new Array(K);
    for (let k = 0; k < K; k++) keys[k] = `${keyField}-${String(k + 1).padStart(6, '0')}`;
    return {
      kind: 'cache-key',
      id,
      seed,
      pii: 'none (synthetic generated keys)',
      cacheProfile: {
        targetHitRatio: target,
        achievedHitRatio: Math.round(achieved * 1e4) / 1e4,
        tolerance: 0.1, // §3.5 cache-hit-ratio dimension
        withinTolerance: Math.abs(achieved - target) <= 0.1,
        clamped,
        keyCardinality: K,
        distribution: 'zipf',
        distributionAlpha: Math.round(alpha * 1e4) / 1e4,
        window: W,
        rate: R,
        ttlSec: T,
        backingStoreSeeded: cp.backingStoreSeeded === true,
      },
      keys,
      cdf,
    };
  }
  // record pool
  const rng = mulberry32(seed);
  const n = poolSpec.count ?? 100;
  const records = new Array(n);
  for (let i = 0; i < n; i++) {
    const rec = {};
    for (const field of poolSpec.fields || []) {
      if (field.optional && rng() < 0.3) continue;
      rec[field.name] = genFieldValue(field, i, rng);
    }
    records[i] = rec;
  }
  return {
    kind: 'record',
    id,
    seed,
    pii: `none (PII-free generators; emails on @${PII_SAFE_DOMAIN})`,
    count: n,
    records,
  };
}
