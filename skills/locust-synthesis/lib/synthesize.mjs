// synthesize.mjs — approved workload-model.json -> locust/ (locustfile.py + lib/
// helpers + feeders/), then run the V2a-equivalent static check. This is the
// Locust SYNTHESIZE boundary (research §4.1, §8 renderer matrix row: Locust).
//
// buildArtifacts() is the PURE core (deterministic, no network, no disk) shared by
// both synthesize() (writes + static-checks) and the formal Renderer adapter
// (lib/renderer.mjs), so the on-disk layout and the renderer files[] never drift —
// the same contract the k6 renderer holds.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generatePool } from '../../k6-synthesis/lib/payloads.mjs';
import { poolKinds } from '../../k6-synthesis/lib/model.mjs';
import { durationToSeconds } from '../../k6-synthesis/lib/arrival.mjs';
import { resolveRequest } from '../../renderer-kit/lib/model-access.mjs';
import { generateLocustfile } from './codegen.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME_DIR = path.join(HERE, '..', 'runtime');
// copied verbatim into locust/lib/ (the generated locustfile imports them)
const RUNTIME_HELPERS = ['__init__.py', 'synthetic.py', 'chain.py', 'think.py', 'pool.py', 'shape.py'];

/** Cache-pool sizing context: combined arrival share of journeys using the pool. */
function poolContext(model, poolId) {
  const spec = model.spec;
  const peakRate = spec.arrivalProfile.stages.reduce((m, s) => Math.max(m, Number(s.rate) || 0), 0);
  const durationSec = spec.arrivalProfile.stages.reduce((s, st) => s + durationToSeconds(st.duration), 0);
  let share = 0;
  for (const j of spec.journeys) {
    if ((j.steps || []).some((s) => resolveRequest(s).bodyPayloadRef === poolId)) share += j.weight;
  }
  share = Math.min(1, share);
  return { ratePerSec: Math.max(1, peakRate * share), ttlSec: 60, durationSec: Math.max(1, durationSec) };
}

/**
 * Build all Locust artifacts IN MEMORY from a model — deterministic, no network.
 * Returns { files, warnings, shape, pools } where files[] paths are RELATIVE to an
 * outDir:  locust/<name>.py, locust/lib/<helper>.py, locust/feeders/<id>.json,
 * locust/requirements.txt.
 */
export function buildArtifacts(model, { ttlSec } = {}) {
  const kinds = poolKinds(model);
  const warnings = [];
  const files = [];

  // 1. feeders (the SAME pre-generated pools the k6 renderer emits, G4)
  const pools = {};
  for (const [id, pspec] of Object.entries((model.spec && model.spec.payloads) || {})) {
    const ctx = poolContext(model, id);
    if (ttlSec) ctx.ttlSec = ttlSec;
    const pool = generatePool(id, pspec, ctx);
    pools[id] = pool;
    files.push({
      path: path.posix.join('locust', 'feeders', `${id}.json`),
      content: JSON.stringify(pool, null, 2) + '\n',
    });
    if (pool.cacheProfile && pool.cacheProfile.withinTolerance === false) {
      warnings.push(
        `feeder "${id}": achieved hit ratio ${pool.cacheProfile.achievedHitRatio} outside tolerance of target ${pool.cacheProfile.targetHitRatio}` +
          (pool.cacheProfile.clamped ? ' (alpha clamped — target unachievable at this K/window)' : '')
      );
    }
  }

  // 2. locustfile + runtime helpers
  const { source, shape, warnings: cgWarn } = generateLocustfile(model, kinds);
  warnings.push(...cgWarn);
  files.push({ path: path.posix.join('locust', `${model.metadata.name}.py`), content: source });
  for (const h of RUNTIME_HELPERS) {
    files.push({
      path: path.posix.join('locust', 'lib', h),
      content: readFileSync(path.join(RUNTIME_DIR, h), 'utf8'),
    });
  }
  files.push({
    path: path.posix.join('locust', 'requirements.txt'),
    content: readFileSync(path.join(RUNTIME_DIR, 'requirements.txt'), 'utf8'),
  });

  return { files, warnings, shape, pools, source };
}

/**
 * Full synthesis: build + write every artifact to disk + run the V2a static check.
 * Returns { model, scriptPath, outDir, pools, shape, v2a, warnings }.
 */
export async function synthesize(modelPathOrObj, outDir, { ttlSec } = {}) {
  const model = typeof modelPathOrObj === 'string'
    ? JSON.parse(readFileSync(modelPathOrObj, 'utf8'))
    : modelPathOrObj;

  const { files, warnings, shape, pools, source } = buildArtifacts(model, { ttlSec });
  for (const f of files) {
    const abs = path.join(outDir, f.path);
    mkdirSync(path.dirname(abs), { recursive: true });
    writeFileSync(abs, f.content);
  }
  const scriptPath = path.join(outDir, 'locust', `${model.metadata.name}.py`);

  const { v2aCheck } = await import('./v2a.mjs');
  const v2a = v2aCheck({ model, source, scriptPath, outDir, shape });

  return { model, scriptPath, outDir, pools, shape, v2a, warnings };
}
