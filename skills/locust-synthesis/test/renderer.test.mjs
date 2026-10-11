// Locust renderer conformance (ISI-5657). Holds the production Locust renderer to
// the SAME shared acceptance harness every renderer uses (ISI-5655), proves it
// renders BOTH the shop-checkout fixture and a real model, that supports() honestly
// declares Locust's approximations (G-O1 open arrival, G-E1 empirical/body_html,
// G-X1 non-http), that synthetic=true rides every request, that request chaining
// is wired + fail-fast, and that the produced locustfile compiles with Python
// (the tool's own checker — V2a).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { locustRenderer } from '../lib/renderer.mjs';
import { synthesize } from '../lib/synthesize.mjs';
import { assertRendererConformance } from '../../renderer-kit/lib/acceptance.mjs';
import { createRegistry } from '../../renderer-kit/lib/registry.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const REAL = path.join(HERE, '..', '..', '..', 'loadtests', 'otel-astronomy-frontend', 'workload-model.json');
const load = (p) => JSON.parse(readFileSync(p, 'utf8'));

test('locust renderer conforms to the shared acceptance harness (interface + determinism)', () => {
  const model = load(FIXTURE);
  const { render } = assertRendererConformance(locustRenderer, model);
  assert.equal(locustRenderer.name, 'locust');
  assert.equal(locustRenderer.targetTool, 'Locust');
  assert.ok(render.files.some((f) => f.path === 'locust/shop-checkout.py'));
  assert.ok(render.files.some((f) => f.path === 'locust/lib/synthetic.py'));
  assert.ok(render.files.some((f) => f.path === 'locust/lib/shape.py'));
  assert.ok(render.files.some((f) => f.path === 'locust/feeders/productId.json'));
  assert.ok(render.files.some((f) => f.path === 'locust/requirements.txt'));
});

test('locust renderer also conforms when rendering the real astronomy model', () => {
  const model = load(REAL);
  const { render } = assertRendererConformance(locustRenderer, model);
  assert.ok(render.files.some((f) => f.path === 'locust/otel-astronomy-frontend.py'));
  // real model carries no approval -> render for PREVIEW with a clear warning
  assert.ok(render.warnings.some((w) => /NOT approved/.test(w)));
});

test('supports() declares the open-arrival (G-O1) approximation for both fixtures', () => {
  for (const p of [FIXTURE, REAL]) {
    const r = locustRenderer.supports(load(p));
    assert.equal(r.ok, false);
    const open = r.unsupported.find((u) => u.feature === 'arrivalProfile.model=open');
    assert.ok(open, 'open-arrival approximation must be declared');
    assert.match(open.approximation, /LoadTestShape/);
    assert.match(open.approximation, /pacing/);
  }
});

test('supports() declares empirical think-time, body_html, and non-http approximations', () => {
  const m = load(FIXTURE);
  m.spec.journeys[0].steps[1].thinkTime = { distribution: 'empirical', samples: [100, 200] };
  m.spec.journeys[0].steps[0].correlates = [
    { sourceStepId: 'x', extract: { from: 'body_html', path: 'a||b' }, inject: { into: 'header', as: 'h' } },
  ];
  m.spec.journeys[0].steps.push({ id: 'g', service: 's', operation: 'rpc', callType: 'grpc' });
  const r = locustRenderer.supports(m);
  const feats = r.unsupported.map((u) => u.feature);
  assert.ok(feats.includes('thinkTime.distribution=empirical'));
  assert.ok(feats.includes('correlates.extract.from=body_html'));
  assert.ok(feats.some((f) => f.startsWith('callType in')));
});

test('every generated request carries synthetic=true baggage', () => {
  const { files } = locustRenderer.render(load(FIXTURE));
  const script = files.find((f) => f.path === 'locust/shop-checkout.py').content;
  const helper = files.find((f) => f.path === 'locust/lib/synthetic.py').content;
  assert.ok(helper.includes('synthetic=true'));
  // every self.client.<verb>( call passes headers=_headers (set from synthetic_headers)
  for (const line of script.split('\n')) {
    if (/self\.client\.(get|post|put|patch|delete|head|options)\(/.test(line)) {
      assert.ok(line.includes('headers=_headers'), `request missing synthetic headers: ${line.trim()}`);
    }
  }
});

test('request chaining is wired with a fail-fast guard (step N consumes step N-1)', () => {
  const { files } = locustRenderer.render(load(FIXTURE));
  const script = files.find((f) => f.path === 'locust/shop-checkout.py').content;
  // checkout: add-to-cart injects productId extracted from view-product
  assert.match(script, /corr0 = require_value\(extract\(responses\.get\('view-product'\)[\s\S]*'add-to-cart', 'productId'\)/);
  // and the extracted value is injected into the next request body
  assert.match(script, /'productId': corr0/);
});

test('real model chaining: header correlation (set-cookie) + path-token feeder binding', () => {
  const { files } = locustRenderer.render(load(REAL));
  const script = files.find((f) => f.path === 'locust/otel-astronomy-frontend.py').content;
  assert.match(script, /extract\(responses\.get\('s2'\), \{"from":"header","path":"set-cookie:session"\}\)/);
  assert.match(script, /synthetic_headers\(\{'cookie': corr0\}\)/);
  // [productId] path token is bound to the cache-key feeder
  assert.match(script, /f'\/api\/products\/\{pick_key\(POOL_product, random\.random\(\)\)\}\/index'/);
});

test('produced locustfile compiles with Python (V2a) — shop-checkout', async () => {
  const out = mkdtempSync(path.join(tmpdir(), 'locust-'));
  try {
    const r = await synthesize(FIXTURE, out);
    assert.equal(r.v2a.pass, true, JSON.stringify(r.v2a.checks.filter((c) => !c.pass), null, 2));
    assert.equal(r.v2a.approved, true);
    assert.ok(r.v2a.checks.find((c) => c.id === 'parse').pass, 'py_compile must pass');
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('produced locustfile compiles with Python (V2a) — real astronomy model', async () => {
  const out = mkdtempSync(path.join(tmpdir(), 'locust-'));
  try {
    const r = await synthesize(REAL, out);
    assert.equal(r.v2a.pass, true, JSON.stringify(r.v2a.checks.filter((c) => !c.pass), null, 2));
    // real model is unapproved -> technical gate passes, approval advisory is false
    assert.equal(r.v2a.approved, false);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('render() files are byte-identical to what synthesize() writes to disk', async () => {
  const out = mkdtempSync(path.join(tmpdir(), 'locust-'));
  try {
    await synthesize(FIXTURE, out);
    const rendered = locustRenderer.render(load(FIXTURE));
    for (const f of rendered.files) {
      const onDisk = readFileSync(path.join(out, f.path), 'utf8');
      assert.equal(f.content, onDisk, `mismatch for ${f.path}`);
    }
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('locust renderer resolves from a registry alongside other tools', () => {
  const reg = createRegistry([locustRenderer]);
  assert.equal(reg.get('locust').name, 'locust');
  assert.equal(reg.get('locust').targetTool, 'Locust');
});
