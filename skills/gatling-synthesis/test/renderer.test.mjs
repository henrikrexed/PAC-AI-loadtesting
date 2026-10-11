// Gatling Renderer-interface conformance (ISI-5658). The Gatling renderer must
// satisfy the SAME shared acceptance harness every renderer uses, render the
// shop-checkout fixture AND the real otel-astronomy model, emit synthetic=true,
// chain requests, and pass its own static check (lint).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gatlingRenderer } from '../lib/renderer.mjs';
import { lintSimulation } from '../lib/lint.mjs';
import { assertRendererConformance } from '../../renderer-kit/lib/acceptance.mjs';
import { createRegistry } from '../../renderer-kit/lib/registry.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const REAL = path.join(HERE, '..', '..', '..', 'loadtests', 'otel-astronomy-frontend', 'workload-model.json');
const shop = JSON.parse(readFileSync(FIXTURE, 'utf8'));
const otel = JSON.parse(readFileSync(REAL, 'utf8'));

function scala(render) {
  return render.files.find((f) => f.path.endsWith('.scala')).content;
}

test('gatling renderer identity + registry', () => {
  assert.equal(gatlingRenderer.name, 'gatling');
  assert.equal(gatlingRenderer.targetTool, 'Gatling');
  const reg = createRegistry([gatlingRenderer]);
  assert.equal(reg.get('gatling').name, 'gatling');
});

test('conforms to the shared acceptance harness on the shop-checkout fixture', () => {
  const { supports, render } = assertRendererConformance(gatlingRenderer, shop);
  // shop-checkout has an exponential think-time -> declared approximation
  assert.equal(supports.ok, false);
  assert.ok(supports.unsupported.some((u) => u.feature === 'thinkTime.distribution=exponential'));
  assert.ok(render.files.some((f) => f.path === 'gatling/ShopCheckoutSimulation.scala'));
  assert.ok(render.files.some((f) => f.path === 'gatling/feeders/productId.json'));
});

test('conforms + renders the REAL otel-astronomy-frontend model', () => {
  const { supports, render } = assertRendererConformance(gatlingRenderer, otel);
  // all-http, native extractors, no think-times -> nothing approximated
  assert.equal(supports.ok, true);
  assert.ok(render.files.some((f) => f.path === 'gatling/OtelAstronomyFrontendSimulation.scala'));
  assert.ok(render.files.some((f) => f.path === 'gatling/feeders/product.json'));
});

test('emits synthetic=true baggage on every request (via the protocol)', () => {
  for (const m of [shop, otel]) {
    const src = scala(gatlingRenderer.render(m));
    assert.match(src, /\.header\("baggage", "synthetic=true"\)/);
  }
});

test('request chaining: step N consumes an id extracted at N-1', () => {
  const src = scala(gatlingRenderer.render(shop));
  // list-products saves products[0].id; view-product consumes it in the path
  assert.match(src, /jsonPath\("\$\.products\[0\]\.id"\)\.saveAs\("c_view_product_id"\)/);
  assert.match(src, /http\("view-product"\)\.get\("\/api\/products\/#\{c_view_product_id\}"\)/);
});

test('header-cookie correlation uses headerRegex (otel buyer journey)', () => {
  const src = scala(gatlingRenderer.render(otel));
  assert.match(src, /headerRegex\("Set-Cookie", "session=\(\[\^;\]\+\)"\)\.saveAs\("c_s3_cookie"\)/);
  assert.match(src, /\.header\("cookie", "#\{c_s3_cookie\}"\)/);
});

test('injection profile maps open arrival -> rate executors, ramps to 0', () => {
  const src = scala(gatlingRenderer.render(shop));
  assert.match(src, /rampUsersPerSec\(0\.0\)\.to\(100\.0\)\.during\(5\.minutes\)/);
  assert.match(src, /constantUsersPerSec\(100\.0\)\.during\(10\.minutes\)/);
  assert.match(src, /rampUsersPerSec\(100\.0\)\.to\(0\.0\)\.during\(5\.minutes\)/);
});

test('journey mix uses .randomSwitch with weights summing to 100', () => {
  const src = scala(gatlingRenderer.render(shop));
  assert.match(src, /\.randomSwitch\(/);
  assert.match(src, /60\.0 -> browse/);
  assert.match(src, /40\.0 -> checkout/);
});

test('think-time: uniform native, exponential/constant as mean pause', () => {
  const src = scala(gatlingRenderer.render(shop));
  assert.match(src, /\.pause\(500\.milliseconds, 1500\.milliseconds\)/); // uniform
  assert.match(src, /\.pause\(2000\.milliseconds\)/); // exponential -> mean
  assert.match(src, /\.pause\(3000\.milliseconds\)/); // constant
});

test('empirical think-time is declared as an approximation (G-E1)', () => {
  const m = JSON.parse(JSON.stringify(shop));
  m.spec.journeys[0].steps[1].thinkTime = { distribution: 'empirical', samples: [100, 300, 1200] };
  const report = gatlingRenderer.supports(m);
  assert.ok(report.unsupported.some((u) => u.feature === 'thinkTime.distribution=empirical'));
});

test('non-http steps reported as not-directly-driven (G-X1)', () => {
  const m = JSON.parse(JSON.stringify(shop));
  m.spec.journeys[0].steps.push({ id: 'cache-read', service: 'c', operation: 'GET x', callType: 'cache' });
  const report = gatlingRenderer.supports(m);
  assert.ok(report.unsupported.some((u) => u.feature.startsWith('callType in')));
});

test("render() warnings mirror the capability report", () => {
  const report = gatlingRenderer.supports(shop);
  const { warnings } = gatlingRenderer.render(shop);
  // every unsupported feature appears in a warning (warnings may also include injection notes)
  for (const u of report.unsupported) {
    assert.ok(warnings.some((w) => w.includes(u.feature)), `missing warning for ${u.feature}`);
  }
});

test('own static check (lint / V2a-equivalent) passes for both fixtures', () => {
  for (const m of [shop, otel]) {
    const lint = lintSimulation(gatlingRenderer.render(m), m);
    assert.ok(lint.pass, `lint failed: ${JSON.stringify(lint.checks.filter((c) => !c.pass))}`);
  }
});
