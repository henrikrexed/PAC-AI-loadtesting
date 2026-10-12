// k6 Renderer-interface conformance. The k6 renderer must satisfy the
// SAME shared acceptance harness every other renderer uses, and its render() must
// produce the identical artifact set that synthesize() writes to disk.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { k6Renderer } from '../lib/renderer.mjs';
import { synthesize } from '../lib/synthesize.mjs';
import { loadModel } from '../lib/model.mjs';
import { assertRendererConformance } from './vendor/acceptance.mjs';
import { createRegistry } from './vendor/registry.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const model = loadModel(FIXTURE);

test('k6 renderer conforms to the shared acceptance harness (interface + determinism)', () => {
  const { supports, render } = assertRendererConformance(k6Renderer, model);
  assert.equal(k6Renderer.name, 'k6');
  assert.equal(k6Renderer.targetTool, 'Grafana k6');
  // fixture is all-http => k6 honors everything
  assert.equal(supports.ok, true);
  assert.equal(supports.unsupported.length, 0);
  // the k6 script + its lib helpers + the payload pools are all present
  assert.ok(render.files.some((f) => f.path === 'k6/shop-checkout.js'));
  assert.ok(render.files.some((f) => f.path === 'k6/lib/baggage.js'));
  assert.ok(render.files.some((f) => f.path === 'payloads/productId.json'));
});

test('k6 renderer reports non-http steps as not-directly-driven (G-X1)', () => {
  const m = JSON.parse(JSON.stringify(model));
  m.spec.journeys[0].steps.push({ id: 'db-read', service: 'db', operation: 'SELECT', callType: 'db' });
  const report = k6Renderer.supports(m);
  assert.equal(report.ok, false);
  assert.ok(report.unsupported.some((u) => u.feature.startsWith('callType in')));
});

test('k6 renderer render() enforces the V1 approval gate', () => {
  const m = loadModel(FIXTURE);
  m.status.revision = 99; // invalidate approval
  assert.throws(() => k6Renderer.render(m), /V1 gate/);
});

test('render() files are byte-identical to what synthesize() writes to disk', () => {
  const out = mkdtempSync(path.join(tmpdir(), 'k6renderer-'));
  try {
    synthesize(FIXTURE, out);
    const rendered = k6Renderer.render(model);
    for (const f of rendered.files) {
      const onDisk = readFileSync(path.join(out, f.path), 'utf8');
      assert.equal(f.content, onDisk, `mismatch for ${f.path}`);
    }
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('k6 renderer resolves from a four-tool registry', () => {
  const reg = createRegistry([k6Renderer]);
  assert.equal(reg.get('k6').name, 'k6');
});
