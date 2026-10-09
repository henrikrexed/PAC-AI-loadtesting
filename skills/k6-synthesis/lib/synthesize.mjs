// synthesize.mjs — orchestrator: approved workload-model.json -> k6/ + payloads/,
// then run the V2a static checker. This is the SYNTHESIZE skill boundary (§3.3,
// §8 row 3): model->k6 codegen, payload-pool generation, G2 chain, V2a.

import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadModel, assertApproved, poolKinds } from './model.mjs';
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
 * Run the full synthesis. Returns { model, scriptPath, outDir, pools, v2a, warnings }.
 * Throws on the V1 gate (unapproved model) before writing anything.
 */
export function synthesize(modelPathOrObj, outDir, { ttlSec } = {}) {
  const model = loadModel(modelPathOrObj);
  assertApproved(model); // V1 gate — refuse unapproved models

  const kinds = poolKinds(model);
  const warnings = [];

  // 1. generate payload pools
  const pools = {};
  const payloadsDir = path.join(outDir, 'payloads');
  mkdirSync(payloadsDir, { recursive: true });
  for (const [id, pspec] of Object.entries((model.spec && model.spec.payloads) || {})) {
    const ctx = poolContext(model, id);
    if (ttlSec) ctx.ttlSec = ttlSec;
    const pool = generatePool(id, pspec, ctx);
    pools[id] = pool;
    writeFileSync(path.join(payloadsDir, `${id}.json`), JSON.stringify(pool, null, 2) + '\n');
    if (pool.cacheProfile && pool.cacheProfile.withinTolerance === false) {
      warnings.push(
        `pool "${id}": achieved hit ratio ${pool.cacheProfile.achievedHitRatio} outside tolerance of target ${pool.cacheProfile.targetHitRatio}` +
          (pool.cacheProfile.clamped ? ' (alpha clamped — target unachievable at this K/window)' : '')
      );
    }
  }

  // 2. generate the k6 script
  const { source, options, maxRate, warnings: cgWarn } = generateScript(model, kinds);
  warnings.push(...cgWarn);
  const k6Dir = path.join(outDir, 'k6');
  const libDir = path.join(k6Dir, 'lib');
  mkdirSync(libDir, { recursive: true });
  for (const h of RUNTIME_HELPERS) cpSync(path.join(RUNTIME_DIR, h), path.join(libDir, h));
  const scriptPath = path.join(k6Dir, `${model.metadata.name}.js`);
  writeFileSync(scriptPath, source);

  // 3. V2a static check
  const v2a = v2aCheck({ model, source, scriptPath, outDir, options, maxRate });

  return { model, scriptPath, outDir, pools, options, maxRate, v2a, warnings };
}
