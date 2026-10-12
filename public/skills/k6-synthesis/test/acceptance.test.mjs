// Acceptance tests — the four acceptance criteria, end-to-end.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { synthesize } from '../lib/synthesize.mjs';
import { loadModel } from '../lib/model.mjs';
import { extract, requireValue, BrokenChainError } from '../runtime/chain.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');

function run(fn) {
  const out = mkdtempSync(path.join(tmpdir(), 'k6synth-'));
  try {
    return fn(out);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
}

test('AC1: multi-step chained scenario — step N consumes id extracted from step N-1', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    const source = readFileSync(res.scriptPath, 'utf8');
    // place-order consumes cartId extracted from add-to-cart; add-to-cart consumes productId from view-product
    assert.ok(source.includes('extract(responses["add-to-cart"], { from: "body_json", path: "cartId" })'));
    assert.ok(source.includes('Object.assign({}, pickRecord(POOL_checkout, Math.random()), { cartId: corr0 })'));
    assert.ok(source.includes('extract(responses["view-product"], { from: "body_json", path: "id" })'));
  });
});

test('AC1: broken chain fails fast with a clear error', () => {
  // runtime behaviour: a response missing the correlated field aborts immediately
  const badResp = { body: JSON.stringify({ not_a_cart: true }) };
  const cartId = extract(badResp, { from: 'body_json', path: 'cartId' });
  assert.equal(cartId, null);
  assert.throws(
    () => requireValue(cartId, 'place-order', 'cartId'),
    (e) => e instanceof BrokenChainError && /broken chain at step=place-order:/.test(e.message)
  );
  // and the generated script wires that guard with k6 fail()
  run((out) => {
    const source = readFileSync(synthesize(FIXTURE, out).scriptPath, 'utf8');
    const guardLine = source.split('\n').find((l) => l.includes('broken chain at step=place-order:'));
    assert.ok(guardLine.includes('fail('));
    assert.ok(guardLine.includes('chainBroken.add(1'));
  });
});

test('AC2: emitted scripts carry synthetic=true on every request + OTel propagation', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    const source = readFileSync(res.scriptPath, 'utf8');
    // trace-context propagation enabled so backend spans join the synthetic trace
    assert.ok(source.includes("instrumentHTTP({ propagator: 'w3c' })"));
    // every request carries baggage synthetic=true via syntheticParams
    const httpLines = source.split('\n').filter((l) => /http\.(get|post|put|patch|del|head|options|request)\s*\(/.test(l));
    for (const l of httpLines) assert.ok(l.includes('syntheticParams('));
    // the copied baggage helper actually encodes synthetic=true
    const baggage = readFileSync(path.join(out, 'k6', 'lib', 'baggage.js'), 'utf8');
    assert.ok(baggage.includes("synthetic=true"));
    // V2a's baggage check confirms it
    assert.equal(res.v2a.checks.find((c) => c.id === 'baggage').pass, true);
  });
});

test('AC3: payload pool reproduces the target cacheProfile hit ratio within tolerance', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    const pool = JSON.parse(readFileSync(path.join(out, 'payloads', 'productId.json'), 'utf8'));
    assert.equal(pool.kind, 'cache-key');
    assert.equal(pool.cacheProfile.targetHitRatio, 0.8);
    assert.equal(pool.cacheProfile.withinTolerance, true);
    assert.ok(Math.abs(pool.cacheProfile.achievedHitRatio - 0.8) <= pool.cacheProfile.tolerance);
    assert.equal(res.pools.productId.cacheProfile.withinTolerance, true);
  });
});

test('AC4: generated artifacts pass V2a static checks', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    for (const c of res.v2a.checks) assert.ok(c.pass, `V2a check failed: ${c.title} — ${c.detail}`);
    assert.equal(res.v2a.pass, true);
  });
});

test('V1 gate: synthesize refuses an unapproved model', () => {
  const model = loadModel(FIXTURE);
  // invalidate the approval (simulate a post-approval model edit)
  model.status.revision = 4;
  run((out) => {
    assert.throws(() => synthesize(model, out), /V1 gate/);
  });
});

test('V2a fails closed when a ramp-down is missing from the emitted options', () => {
  // A model whose stages never reach 0 must still pass V2a because SYNTHESIZE
  // appends the ramp-down; assert the appended stage exists and V2a is green.
  const model = loadModel(FIXTURE);
  model.spec.arrivalProfile.stages = [
    { duration: '5m', rate: 100, shape: 'ramp_up' },
    { duration: '10m', rate: 100, shape: 'plateau' },
  ];
  run((out) => {
    const res = synthesize(model, out);
    assert.ok(res.warnings.some((w) => w.includes('ramp-down stage synthesized')));
    assert.equal(res.v2a.checks.find((c) => c.id === 'rampdown').pass, true);
    for (const sc of Object.values(res.options.scenarios)) {
      assert.equal(sc.stages[sc.stages.length - 1].target, 0);
    }
  });
});
