// synthesize.mjs — orchestrator: approved workload-model.json -> k6/ + payloads/,
// then run the V2a static checker. This is the SYNTHESIZE skill boundary (§3.3,
// §8 row 3): model->k6 codegen, payload-pool generation, G2 chain, V2a.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadModel, assertApproved, assertNotDemo, poolKinds } from './model.mjs';
import { generatePool } from './payloads.mjs';
import { generateScript } from './codegen.mjs';
import { durationToSeconds } from './arrival.mjs';
import { v2aCheck } from './v2a.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME_DIR = path.join(HERE, '..', 'runtime');
const RUNTIME_HELPERS = ['baggage.js', 'chain.js', 'session.js', 'pool.js', 'think.js'];

/**
 * Compute the cache-pool sizing context for a payload pool: which journeys use
 * it, their combined arrival share, and the run peak rate / duration.
 */
function poolContext(model, poolId) {
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

/**
 * Build all k6 artifacts IN MEMORY from an approved model — deterministic, no
 * network, no disk writes. This is the pure core that both `synthesize()` (which
 * writes + runs V2a) and the formal Renderer adapter (`lib/renderer.mjs`, §4.3)
 * share, so the on-disk layout and the renderer `files[]` never drift.
 *
 * Returns { pools, options, maxRate, warnings, files } where `files` is an array
 * of { path, content } with paths RELATIVE to an outDir:
 *   payloads/<id>.json, k6/<name>.js, k6/lib/<helper>.js
 */
export function buildArtifacts(model, { ttlSec } = {}) {
  const kinds = poolKinds(model);
  const warnings = [];
  const files = [];

  // 1. payload pools
  const pools = {};
  for (const [id, pspec] of Object.entries((model.spec && model.spec.payloads) || {})) {
    const ctx = poolContext(model, id);
    if (ttlSec) ctx.ttlSec = ttlSec;
    const pool = generatePool(id, pspec, ctx);
    pools[id] = pool;
    files.push({ path: path.posix.join('payloads', `${id}.json`), content: JSON.stringify(pool, null, 2) + '\n' });
    if (pool.cacheProfile && pool.cacheProfile.withinTolerance === false) {
      warnings.push(
        `pool "${id}": achieved hit ratio ${pool.cacheProfile.achievedHitRatio} outside tolerance of target ${pool.cacheProfile.targetHitRatio}` +
          (pool.cacheProfile.clamped ? ' (alpha clamped — target unachievable at this K/window)' : '')
      );
    }
  }

  // 2. k6 script + runtime helpers
  const { source, options, maxRate, warnings: cgWarn } = generateScript(model, kinds);
  warnings.push(...cgWarn);
  files.push({ path: path.posix.join('k6', `${model.metadata.name}.js`), content: source });
  for (const h of RUNTIME_HELPERS) {
    files.push({ path: path.posix.join('k6', 'lib', h), content: readFileSync(path.join(RUNTIME_DIR, h), 'utf8') });
  }

  return { pools, options, maxRate, warnings, files, source };
}

/**
 * Run the full synthesis. Returns { model, scriptPath, outDir, pools, v2a, warnings }.
 * Throws on the V1 gate (unapproved model) before writing anything.
 */
export function synthesize(modelPathOrObj, outDir, { ttlSec, allowDemo } = {}) {
  const model = loadModel(modelPathOrObj);
  // ISI-5928 demo guard — BEFORE V1: demo data is refused even if a (hand-edited)
  // approval block is present, unless the operator explicitly opted in.
  const { provenanceWarning } = assertNotDemo(model, { allowDemo });
  assertApproved(model); // V1 gate — refuse unapproved models
  const warnings = provenanceWarning ? [provenanceWarning] : [];

  const { pools, options, maxRate, warnings: buildWarnings, files, source } = buildArtifacts(model, { ttlSec });
  warnings.push(...buildWarnings);

  // write every artifact to disk, preserving the relative layout
  for (const f of files) {
    const abs = path.join(outDir, f.path);
    mkdirSync(path.dirname(abs), { recursive: true });
    writeFileSync(abs, f.content);
  }
  const scriptPath = path.join(outDir, 'k6', `${model.metadata.name}.js`);

  // V2a static check (reads the just-written files on disk)
  const v2a = v2aCheck({ model, source, scriptPath, outDir, options, maxRate });

  return { model, scriptPath, outDir, pools, options, maxRate, v2a, warnings };
}
