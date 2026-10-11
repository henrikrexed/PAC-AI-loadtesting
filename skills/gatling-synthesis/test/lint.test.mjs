// lint.mjs unit tests — the Gatling renderer's own static check (V2a-equivalent).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gatlingRenderer } from '../lib/renderer.mjs';
import { lintSimulation } from '../lib/lint.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const shop = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json'), 'utf8'));

function render() {
  return gatlingRenderer.render(shop);
}

test('lint passes on a clean render', () => {
  const lint = lintSimulation(render(), shop);
  assert.ok(lint.pass);
  // every check id present
  for (const id of ['balance', 'synthetic', 'feeders', 'chain', 'rampdown', 'caps', 'weights']) {
    assert.ok(lint.checks.some((c) => c.id === id), `missing check ${id}`);
  }
});

test('lint FAILS when the synthetic baggage header is stripped', () => {
  const r = render();
  const f = r.files.find((x) => x.path.endsWith('.scala'));
  f.content = f.content.replace('.header("baggage", "synthetic=true")', '');
  const lint = lintSimulation(r, shop);
  assert.equal(lint.pass, false);
  assert.ok(lint.checks.find((c) => c.id === 'synthetic' && !c.pass));
});

test('lint FAILS on a broken correlation chain (dangling reference)', () => {
  const r = render();
  const f = r.files.find((x) => x.path.endsWith('.scala'));
  // drop a saveAs but keep its #{ref} -> dangling
  f.content = f.content.replace('.check(jsonPath("$.products[0].id").saveAs("c_view_product_id"))', '');
  const lint = lintSimulation(r, shop);
  assert.equal(lint.pass, false);
  assert.ok(lint.checks.find((c) => c.id === 'chain' && !c.pass));
});

test('lint FAILS when a referenced feeder file is missing', () => {
  const r = render();
  r.files = r.files.filter((x) => x.path !== 'gatling/feeders/productId.json');
  const lint = lintSimulation(r, shop);
  assert.equal(lint.pass, false);
  assert.ok(lint.checks.find((c) => c.id === 'feeders' && !c.pass));
});

test('lint FAILS when peak rate exceeds caps.maxRps', () => {
  const m = JSON.parse(JSON.stringify(shop));
  m.spec.caps.maxRps = 10; // below the fixture peak of 100
  const lint = lintSimulation(gatlingRenderer.render(m), m);
  assert.equal(lint.pass, false);
  assert.ok(lint.checks.find((c) => c.id === 'caps' && !c.pass));
});
