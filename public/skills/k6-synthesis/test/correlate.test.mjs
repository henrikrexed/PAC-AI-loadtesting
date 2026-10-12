import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseOperation,
  methodHasBody,
  renderCorrelations,
  renderUrl,
  renderBody,
  renderHeaderInjections,
} from '../lib/correlate.mjs';

test('parseOperation splits method + path', () => {
  assert.deepEqual(parseOperation('GET /api/products/{id}'), { method: 'GET', path: '/api/products/{id}' });
  assert.deepEqual(parseOperation('POST /api/cart'), { method: 'POST', path: '/api/cart' });
  assert.equal(methodHasBody('POST'), true);
  assert.equal(methodHasBody('GET'), false);
});

test('renderCorrelations emits an extract + fail-fast guard per correlate', () => {
  const step = {
    id: 'place-order',
    correlates: [
      { sourceStepId: 'add-to-cart', extract: { from: 'body_json', path: 'cartId' }, inject: { into: 'body_field', as: 'cartId' } },
    ],
  };
  const { lines, injections } = renderCorrelations(step);
  const src = lines.join('\n');
  assert.ok(src.includes("extract(responses[\"add-to-cart\"]"));
  assert.ok(src.includes('broken chain at step=place-order:'));
  assert.ok(src.includes('fail('));
  assert.deepEqual(injections[0], { into: 'body_field', as: 'cartId', expr: 'corr0' });
});

test('renderUrl applies path_param and cache-key injections', () => {
  const inj = [{ into: 'path_param', as: 'id', expr: 'corr0' }];
  const url = renderUrl('BASE', '/api/products/{id}', inj, null);
  assert.equal(url, '`${BASE}/api/products/${encodeURIComponent(corr0)}`');

  const urlPool = renderUrl('BASE', '/api/products/{id}', [], 'pickKey(POOL_productId, Math.random())');
  assert.ok(urlPool.includes('encodeURIComponent(pickKey(POOL_productId, Math.random()))'));
});

test('renderUrl appends query_param injections', () => {
  const url = renderUrl('BASE', '/api/search', [{ into: 'query_param', as: 'q', expr: 'corr0' }], null);
  assert.ok(url.includes('?q=${encodeURIComponent(corr0)}'));
});

test('renderBody layers body_field injections over a payload record', () => {
  const body = renderBody('pickRecord(POOL_cartItem, Math.random())', [{ into: 'body_field', as: 'productId', expr: 'corr0' }]);
  assert.equal(body, 'Object.assign({}, pickRecord(POOL_cartItem, Math.random()), { productId: corr0 })');
  assert.equal(renderBody(null, []), null);
  assert.equal(renderBody('{}', []), '{}');
});

test('renderHeaderInjections quotes non-identifier header names', () => {
  assert.equal(renderHeaderInjections([]), '{}');
  assert.equal(renderHeaderInjections([{ into: 'header', as: 'X-Auth-Token', expr: 'corr0' }]), '{ "X-Auth-Token": corr0 }');
  assert.equal(renderHeaderInjections([{ into: 'header', as: 'authorization', expr: 'corr1' }]), '{ authorization: corr1 }');
});
