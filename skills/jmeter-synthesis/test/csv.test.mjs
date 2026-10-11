// Unit tests for CSV data set generation (csv.mjs).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildDataset, buildDatasets, poolVarName } from '../lib/csv.mjs';
import { loadModel } from '../lib/model.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const model = loadModel(FIXTURE);

test('cache-key pool -> materialized Zipf sample CSV', () => {
  const ds = buildDataset(model, 'productId', model.spec.payloads.productId);
  assert.equal(ds.kind, 'cache-key');
  assert.equal(ds.keyField, 'id');
  assert.deepEqual(ds.variableNames, ['productId__id']);
  const rows = ds.content.trim().split('\n');
  assert.equal(rows[0], 'id');
  assert.equal(rows.length - 1, ds.sampleRows);
  // Zipf: the single most popular key dominates the sample
  const counts = new Map();
  for (const r of rows.slice(1)) counts.set(r, (counts.get(r) || 0) + 1);
  const top = [...counts.values()].sort((a, b) => b - a)[0];
  assert.ok(top / ds.sampleRows > 0.1, 'top key should carry a heavy Zipf share');
});

test('record pool -> one row per record, one column per field', () => {
  const ds = buildDataset(model, 'checkout', model.spec.payloads.checkout);
  assert.equal(ds.kind, 'record');
  assert.deepEqual(ds.columns, ['email', 'currency']);
  assert.deepEqual(ds.variableNames, ['checkout__email', 'checkout__currency']);
  const rows = ds.content.trim().split('\n');
  assert.equal(rows[0], 'email,currency');
  // emails are PII-free synthetic (@synthetic.invalid)
  assert.match(rows[1], /@synthetic\.invalid/);
});

test('data sets are deterministic (byte-identical across builds)', () => {
  const a = buildDatasets(model);
  const b = buildDatasets(model);
  for (const id of Object.keys(a)) assert.equal(a[id].content, b[id].content);
});

test('poolVarName namespaces to avoid cross-pool collisions', () => {
  assert.equal(poolVarName('productId', 'id'), 'productId__id');
  assert.equal(poolVarName('cart-item', 'qty.n'), 'cart_item__qty_n');
});
