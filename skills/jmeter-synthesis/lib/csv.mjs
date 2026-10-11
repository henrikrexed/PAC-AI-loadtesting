// csv.mjs — payload pools -> JMeter CSV Data Sets (G4 cache-avoidance, §4.1).
//
// JMeter has no runtime distribution sampler without JSR223, so the renderer
// PRE-GENERATES the data set and lets a native CSV Data Set Config feed it (the
// research-§4.1 strategy: "pre-generated Zipf key pool -> CSV Data Set Config").
//
//   * cache-key pool  -> a MATERIALIZED Zipf sample: N key rows drawn by
//     inverse-transform from the pool CDF (seeded, deterministic). Read in order
//     with recycle, the sequence reproduces production key popularity -> the
//     target cache hit ratio. One column: the key field.
//   * record pool     -> one row per synthetic record, one column per field.
//
// The pool math (Zipf fit, cache sizing, PII-free field generators) is REUSED
// from k6-synthesis so the two renderers bake identical pools from the same model
// (single source of truth — no drift).

import { generatePool, mulberry32, simulateHitRatio } from '../../k6-synthesis/lib/payloads.mjs';
import { durationToSeconds } from '../../k6-synthesis/lib/arrival.mjs';

/** JMeter variable name for a pool field — namespaced so two pools never collide. */
export function poolVarName(poolId, fieldName) {
  return `${sanitize(poolId)}__${sanitize(fieldName)}`;
}

function sanitize(s) {
  return String(s).replace(/[^A-Za-z0-9_]/g, '_');
}

/** RFC4180-style CSV cell quoting. */
function csvCell(v) {
  const s = v == null ? '' : String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvRows(rows) {
  return rows.map((r) => r.map(csvCell).join(',')).join('\n') + '\n';
}

/**
 * Cache-pool sizing context (mirrors k6-synthesis/synthesize.poolContext): which
 * journeys use the pool, their combined arrival share, and the run peak rate /
 * duration — so the pool reproduces the right popularity window.
 */
export function poolContext(model, poolId) {
  const spec = model.spec;
  const peakRate = spec.arrivalProfile.stages.reduce((m, s) => Math.max(m, Number(s.rate) || 0), 0);
  const durationSec = spec.arrivalProfile.stages.reduce((sum, s) => sum + durationToSeconds(s.duration), 0);
  let share = 0;
  for (const j of spec.journeys) {
    if ((j.steps || []).some((s) => s.payloadRef === poolId)) share += j.weight;
  }
  share = Math.min(1, share);
  return { ratePerSec: Math.max(1, peakRate * share), ttlSec: 60, durationSec: Math.max(1, durationSec) };
}

/** Clamp the materialized cache-sample size: >> the popularity window, bounded. */
function sampleSize(window) {
  return Math.min(8000, Math.max(1000, Math.round(window * 4)));
}

/** Inverse-transform draw of an index from a cumulative CDF (binary search). */
function drawIndex(cdf, r) {
  let lo = 0;
  let hi = cdf.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (r <= cdf[mid]) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

/**
 * Build a CSV data set for one payload pool.
 * Returns {
 *   id, kind, filename, columns, variableNames, recycle, content,
 *   keyField?, cacheProfile?   // cache-key pools only
 * }.
 */
export function buildDataset(model, poolId, poolSpec) {
  const ctx = poolContext(model, poolId);
  const pool = generatePool(poolId, poolSpec, ctx);
  const filename = `${poolId}.csv`;

  if (pool.kind === 'cache-key') {
    const cp = pool.cacheProfile;
    const keyField = (poolSpec.fields && poolSpec.fields[0] && poolSpec.fields[0].name) || 'id';
    const seed = poolSpec.seed ?? 1;
    const N = sampleSize(cp.window);
    const rng = mulberry32(seed);
    const dataRows = new Array(N);
    for (let i = 0; i < N; i++) dataRows[i] = [pool.keys[drawIndex(pool.cdf, rng())]];
    // informational: the hit ratio this materialized sequence realizes in-window.
    const achievedSampled = Math.round(simulateHitRatio({ cdf: pool.cdf, W: cp.window, N, seed }) * 1e4) / 1e4;
    const content = csvRows([[keyField], ...dataRows]);
    return {
      id: poolId,
      kind: 'cache-key',
      filename,
      columns: [keyField],
      variableNames: [poolVarName(poolId, keyField)],
      recycle: true,
      content,
      keyField,
      sampleRows: N,
      cacheProfile: { ...cp, achievedHitRatioSampled: achievedSampled },
    };
  }

  // record pool — one column per field, one row per record.
  const fields = (poolSpec.fields || []).map((f) => f.name);
  const columns = fields.length ? fields : ['value'];
  const dataRows = (pool.records || []).map((rec) => columns.map((c) => (c in rec ? rec[c] : '')));
  const content = csvRows([columns, ...dataRows]);
  return {
    id: poolId,
    kind: 'record',
    filename,
    columns,
    variableNames: columns.map((c) => poolVarName(poolId, c)),
    recycle: true,
    content,
    recordCount: dataRows.length,
    pii: pool.pii,
  };
}

/** Build every data set referenced by the model, keyed by pool id. */
export function buildDatasets(model) {
  const out = {};
  for (const [id, spec] of Object.entries((model.spec && model.spec.payloads) || {})) {
    out[id] = buildDataset(model, id, spec);
  }
  return out;
}
