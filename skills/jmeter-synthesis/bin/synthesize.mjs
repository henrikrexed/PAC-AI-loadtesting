#!/usr/bin/env node
// bin/synthesize.mjs — CLI: render an approved workload-model.json to a JMeter
// test plan + CSV data sets, then run the static check.
//   node bin/synthesize.mjs <model.json> <outDir>

import { synthesize } from '../lib/synthesize.mjs';

const [, , modelPath, outDir] = process.argv;
if (!modelPath || !outDir) {
  console.error('usage: node bin/synthesize.mjs <model.json> <outDir>');
  process.exit(2);
}

try {
  const res = synthesize(modelPath, outDir);
  console.log(`jmeter-synthesis: wrote ${res.files.length} file(s) to ${outDir}`);
  for (const f of res.files) console.log(`  ${f.path}`);
  for (const w of res.warnings) console.log(`  warning: ${w}`);
  console.log(`\nstatic check: ${res.check.pass ? 'PASS' : 'FAIL'}`);
  for (const c of res.check.checks) {
    console.log(`  [${c.pass ? 'ok' : 'XX'}] ${c.title} — ${c.detail}`);
  }
  process.exit(res.check.pass ? 0 : 1);
} catch (e) {
  console.error(`jmeter-synthesis: ${e.message}`);
  process.exit(1);
}
