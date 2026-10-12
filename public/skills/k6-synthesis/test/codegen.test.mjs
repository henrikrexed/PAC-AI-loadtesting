import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadModel, poolKinds } from '../lib/model.mjs';
import { generateScript } from '../lib/codegen.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');

function gen() {
  const model = loadModel(FIXTURE);
  return generateScript(model, poolKinds(model));
}

test('generates one scenario + one exec function per journey', () => {
  const { source, options } = gen();
  assert.deepEqual(Object.keys(options.scenarios).sort(), ['browse', 'checkout']);
  assert.equal(options.scenarios.browse.exec, 'browse');
  assert.equal(options.scenarios.checkout.exec, 'checkout');
  assert.ok(source.includes('export function browse()'));
  assert.ok(source.includes('export function checkout()'));
});

test('enables OTel propagation and imports helpers + pools', () => {
  const { source } = gen();
  assert.ok(source.includes("instrumentHTTP({ propagator: 'w3c' })"));
  assert.ok(source.includes("import { syntheticParams } from './lib/baggage.js'"));
  assert.ok(source.includes("import { resetUserSession } from './lib/session.js'"));
  assert.ok(source.includes("import POOL_productId from '../payloads/productId.json'"));
  assert.ok(source.includes("import POOL_checkout from '../payloads/checkout.json'"));
});

test('checkout scenario ramps down to 0 and rate is weight-scaled', () => {
  const { options, maxRate } = gen();
  const co = options.scenarios.checkout;
  assert.equal(co.executor, 'ramping-arrival-rate');
  assert.equal(co.stages[0].target, 40); // 100 * 0.4
  assert.equal(co.stages[co.stages.length - 1].target, 0);
  const br = options.scenarios.browse;
  assert.equal(br.stages[0].target, 60); // 100 * 0.6
  assert.equal(Math.round(maxRate), 100);
});

test('every http request routes through syntheticParams (baggage synthetic=true)', () => {
  const { source } = gen();
  const httpLines = source.split('\n').filter((l) => /http\.(get|post|put|patch|del|head|options|request)\s*\(/.test(l));
  assert.ok(httpLines.length >= 5); // 2 browse + 3 checkout steps
  for (const l of httpLines) assert.ok(l.includes('syntheticParams('), `no syntheticParams in: ${l}`);
});

test('chained step injects correlated id and guards the chain', () => {
  const { source } = gen();
  // checkout: add-to-cart injects productId from view-product; place-order injects cartId from add-to-cart
  assert.ok(source.includes('extract(responses["view-product"]'));
  assert.ok(source.includes('extract(responses["add-to-cart"]'));
  assert.ok(source.includes('broken chain at step=add-to-cart:'));
  assert.ok(source.includes('broken chain at step=place-order:'));
  // cache-key pool bound into the view-product path param
  assert.ok(source.includes('pickKey(POOL_productId, Math.random())'));
});
