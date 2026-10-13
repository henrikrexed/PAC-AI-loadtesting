#!/usr/bin/env node
// CLI: k6-synthesis — generate k6 scripts + payload pools from an approved
// workload model and run the V2a static checker.
//
//   node bin/synthesize.mjs <workload-model.json> <output-dir> [--ttl <sec>]
//
// Exit code 0 iff V2a passes; non-zero otherwise (so CI / the loop can gate).

import { synthesize } from '../lib/synthesize.mjs';

function parseArgs(argv) {
  const pos = [];
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--ttl') opts.ttlSec = Number(argv[++i]);
    else pos.push(argv[i]);
  }
  return { modelPath: pos[0], outDir: pos[1], opts };
}

function main() {
  const { modelPath, outDir, opts } = parseArgs(process.argv.slice(2));
  if (!modelPath || !outDir) {
    console.error('usage: synthesize.mjs <workload-model.json> <output-dir> [--ttl <sec>]');
    process.exit(2);
  }
  let res;
  try {
    res = synthesize(modelPath, outDir, opts);
  } catch (e) {
    console.error(`SYNTHESIZE failed: ${e.message}`);
    process.exit(1);
  }

  console.log(`model:   ${res.model.metadata.name} rev ${res.model.status.revision}`);
  console.log(`script:  ${res.scriptPath}`);
  console.log(`pools:   ${Object.keys(res.pools).join(', ') || '(none)'}`);
  for (const [id, pool] of Object.entries(res.pools)) {
    if (pool.cacheProfile) {
      const cp = pool.cacheProfile;
      console.log(`  ${id}: cache-key K=${cp.keyCardinality} zipf-alpha=${cp.distributionAlpha} hit=${cp.achievedHitRatio} (target ${cp.targetHitRatio})`);
    }
  }
  if (res.warnings.length) {
    console.log('warnings:');
    for (const w of res.warnings) console.log(`  - ${w}`);
  }
  console.log(`\nV2a: ${res.v2a.pass ? 'PASS' : 'FAIL'}`);
  for (const c of res.v2a.checks) {
    console.log(`  [${c.pass ? 'x' : ' '}] ${c.title} — ${c.detail}`);
  }
  process.exit(res.v2a.pass ? 0 : 1);
}

main();
