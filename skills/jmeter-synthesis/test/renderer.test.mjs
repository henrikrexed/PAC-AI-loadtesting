// JMeter Renderer-interface conformance (ISI-5656 / ISI-5655 harness). The JMeter
// renderer must satisfy the SAME shared acceptance harness every other renderer
// uses, render BOTH the shop-checkout fixture and one real model, and its render()
// must be byte-identical to what synthesize() writes to disk.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { jmeterRenderer } from '../lib/renderer.mjs';
import { synthesize } from '../lib/synthesize.mjs';
import { loadModel } from '../lib/model.mjs';
import { assertRendererConformance } from '../../renderer-kit/lib/acceptance.mjs';
import { createRegistry } from '../../renderer-kit/lib/registry.mjs';
import { k6Renderer } from '../../k6-synthesis/lib/renderer.mjs';
import { locustStub } from '../../renderer-kit/lib/renderers/locust-stub.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const REAL = path.join(HERE, '..', '..', '..', 'loadtests', 'otel-astronomy-frontend', 'workload-model.json');

const model = loadModel(FIXTURE);

/** The committed real model carries no approval block; inject one for the render
 * (its revision is authentic). This is the same in-memory approval the k6
 * acceptance tests use to exercise a model through the V1 gate. */
function approvedRealModel() {
  const m = loadModel(REAL);
  m.status.approval = {
    revision: m.status.revision,
    decision: 'approved',
    decisionBy: 'acceptance-test',
    decisionAt: '2026-10-11T00:00:00Z',
  };
  return m;
}

test('jmeter renderer conforms to the shared acceptance harness (shop-checkout)', () => {
  const { supports, render } = assertRendererConformance(jmeterRenderer, model);
  assert.equal(jmeterRenderer.name, 'jmeter');
  assert.equal(jmeterRenderer.targetTool, 'Apache JMeter');
  // all-http, no empirical/body_html => JMeter honors everything in this fixture
  assert.equal(supports.ok, true);
  assert.equal(supports.unsupported.length, 0);
  assert.ok(render.files.some((f) => f.path === 'jmeter/shop-checkout.jmx'));
  assert.ok(render.files.some((f) => f.path === 'jmeter/data/productId.csv'));
  assert.ok(render.files.some((f) => f.path === 'jmeter/data/checkout.csv'));
  assert.ok(render.files.some((f) => f.path === 'jmeter/shop-checkout.manifest.json'));
});

test('jmeter renderer conforms to the harness on a real model (otel-astronomy-frontend)', () => {
  const real = approvedRealModel();
  const { render } = assertRendererConformance(jmeterRenderer, real);
  assert.ok(render.files.some((f) => f.path === 'jmeter/otel-astronomy-frontend.jmx'));
  assert.ok(render.files.some((f) => f.path === 'jmeter/data/product.csv'));
});

test('supports() lists the JMeter approximations (empirical JSR223 + body_html Boundary)', () => {
  const m = JSON.parse(JSON.stringify(model));
  m.spec.journeys[0].steps[1].thinkTime = { distribution: 'empirical', meanMs: 1000 };
  m.spec.journeys[1].steps[1].correlates[0].extract = { from: 'body_html', path: 'div.cart#id' };
  const report = jmeterRenderer.supports(m);
  assert.equal(report.ok, false);
  assert.ok(report.unsupported.some((u) => u.feature === 'thinkTime.distribution=empirical' && /JSR223/.test(u.approximation)));
  assert.ok(report.unsupported.some((u) => u.feature === 'correlates.extract.from=body_html' && /Boundary/.test(u.approximation)));
});

test('supports() reports non-http steps as not-directly-driven (G-X1)', () => {
  const m = JSON.parse(JSON.stringify(model));
  m.spec.journeys[0].steps.push({ id: 'db-read', service: 'db', operation: 'SELECT', callType: 'db' });
  const report = jmeterRenderer.supports(m);
  assert.equal(report.ok, false);
  assert.ok(report.unsupported.some((u) => u.feature.startsWith('callType in')));
});

test('render() enforces the V1 approval gate', () => {
  const m = loadModel(FIXTURE);
  m.status.revision = 99; // invalidate approval
  assert.throws(() => jmeterRenderer.render(m), /V1 gate/);
});

test('render() files are byte-identical to what synthesize() writes to disk', () => {
  const out = mkdtempSync(path.join(tmpdir(), 'jmeterrenderer-'));
  try {
    synthesize(FIXTURE, out);
    const rendered = jmeterRenderer.render(model);
    for (const f of rendered.files) {
      const onDisk = readFileSync(path.join(out, f.path), 'utf8');
      assert.equal(f.content, onDisk, `mismatch for ${f.path}`);
    }
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('jmeter resolves from a multi-tool registry alongside k6 + locust', () => {
  const reg = createRegistry([k6Renderer, jmeterRenderer, locustStub]);
  assert.deepEqual(reg.names().sort(), ['jmeter', 'k6', 'locust']);
  assert.equal(reg.get('jmeter').targetTool, 'Apache JMeter');
});
