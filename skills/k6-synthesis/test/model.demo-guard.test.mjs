// Demo-data quarantine guard (ISI-5928): a provenance.kind="demo-sample" model is
// refused by synthesize()/render() unless the operator explicitly opts in
// (--demo -> allowDemo, or WORKLOAD_MODEL_ALLOW_DEMO=1). Legacy models with no
// provenance warn instead of failing (back-compat).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotDemo, loadModel } from '../lib/model.mjs';
import { synthesize } from '../lib/synthesize.mjs';
import { k6Renderer } from '../lib/renderer.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');

function demoModel() {
  const m = JSON.parse(readFileSync(FIXTURE, 'utf8'));
  m.metadata.source.provenance = {
    kind: 'demo-sample',
    note: 'synthetic example — not extracted from any tenant',
  };
  return m;
}

test('demo-sample model is refused by synthesize() without opt-in', () => {
  const m = demoModel();
  assert.throws(() => synthesize(m, '/tmp/never-written'), /demo guard \(ISI-5928\)/);
});

test('demo-sample model is refused by the renderer without opt-in', () => {
  const m = demoModel();
  assert.throws(() => k6Renderer.render(m), /demo guard \(ISI-5928\)/);
});

test('explicit allowDemo opt-in unblocks synthesize()', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'k6-demo-'));
  const res = synthesize(demoModel(), dir, { allowDemo: true });
  assert.ok(res.scriptPath);
});

test('WORKLOAD_MODEL_ALLOW_DEMO=1 env var also opts in', () => {
  process.env.WORKLOAD_MODEL_ALLOW_DEMO = '1';
  try {
    const dir = mkdtempSync(path.join(tmpdir(), 'k6-demo-env-'));
    const res = synthesize(demoModel(), dir);
    assert.ok(res.scriptPath);
  } finally {
    delete process.env.WORKLOAD_MODEL_ALLOW_DEMO;
  }
});

test('legacy model without provenance warns but does not fail', () => {
  const m = loadModel(FIXTURE); // fixture carries no provenance
  const { provenanceWarning } = assertNotDemo(m);
  assert.match(provenanceWarning, /no provenance/);
});
