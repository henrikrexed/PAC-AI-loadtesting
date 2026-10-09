// Unit tests for the pure runtime helpers (chain, baggage, think).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { extract, resolvePath, failChain, requireValue, BrokenChainError } from '../runtime/chain.js';
import { syntheticParams, mergeBaggage, carriesSynthetic, SYNTHETIC_BAGGAGE } from '../runtime/baggage.js';
import { thinkSeconds } from '../runtime/think.js';

test('resolvePath handles dotted + bracketed paths and missing segments', () => {
  const obj = { products: [{ id: 'p1' }, { id: 'p2' }], meta: { cartId: 'c9' } };
  assert.equal(resolvePath(obj, 'products[0].id'), 'p1');
  assert.equal(resolvePath(obj, 'products[1].id'), 'p2');
  assert.equal(resolvePath(obj, 'meta.cartId'), 'c9');
  assert.equal(resolvePath(obj, 'meta.missing'), null);
  assert.equal(resolvePath(obj, 'products[9].id'), null);
  assert.equal(resolvePath(null, 'x'), null);
});

test('extract: body_json parses string body and returns null when absent', () => {
  const res = { body: JSON.stringify({ id: 'abc', nested: { v: 1 } }) };
  assert.equal(extract(res, { from: 'body_json', path: 'id' }), 'abc');
  assert.equal(extract(res, { from: 'body_json', path: 'nested.v' }), 1);
  assert.equal(extract(res, { from: 'body_json', path: 'missing' }), null);
  assert.equal(extract({ body: 'not json' }, { from: 'body_json', path: 'id' }), null);
});

test('extract: header (case-insensitive), body_html, body_regex', () => {
  assert.equal(extract({ headers: { Location: '/x/42' } }, { from: 'header', path: 'location' }), '/x/42');
  assert.equal(extract({ body: 'a<b>TOK</b>c' }, { from: 'body_html', path: '<b>||</b>' }), 'TOK');
  assert.equal(extract({ body: 'id=777;' }, { from: 'body_regex', path: 'id=(\\d+)' }), '777');
  assert.equal(extract({ body: 'no match' }, { from: 'body_regex', path: 'id=(\\d+)' }), null);
});

test('failChain / requireValue raise BrokenChainError on null (fail-fast)', () => {
  assert.throws(() => failChain('step-x', 'cartId'), BrokenChainError);
  assert.throws(() => requireValue(null, 'step-x', 'cartId'), (e) => e instanceof BrokenChainError && e.stepId === 'step-x');
  assert.equal(requireValue('ok', 'step-x', 'cartId'), 'ok');
});

test('syntheticParams always sets baggage synthetic=true + tag', () => {
  const p = syntheticParams();
  assert.equal(p.headers.baggage, SYNTHETIC_BAGGAGE);
  assert.equal(p.tags.synthetic, 'true');
  // merges extra headers and forces synthetic even if caller passes other baggage
  const p2 = syntheticParams({ baggage: 'tenant=acme', Authorization: 'Bearer x' });
  assert.ok(carriesSynthetic(p2.headers.baggage));
  assert.ok(p2.headers.baggage.includes('tenant=acme'));
  assert.equal(p2.headers.Authorization, 'Bearer x');
});

test('mergeBaggage de-dups synthetic and preserves others', () => {
  assert.equal(mergeBaggage(undefined), 'synthetic=true');
  assert.equal(mergeBaggage('synthetic=false'), 'synthetic=true');
  assert.equal(mergeBaggage('a=1,synthetic=true,b=2'), 'a=1,b=2,synthetic=true');
  assert.ok(carriesSynthetic('a=1,synthetic=true'));
  assert.ok(!carriesSynthetic('a=1'));
});

test('thinkSeconds honours distributions', () => {
  assert.equal(thinkSeconds({ distribution: 'constant', meanMs: 3000 }, 0.5), 3);
  assert.equal(thinkSeconds({ distribution: 'uniform', minMs: 500, maxMs: 1500 }, 0.5), 1);
  assert.ok(thinkSeconds({ distribution: 'exponential', meanMs: 2000 }, 0.5) > 0);
  assert.equal(thinkSeconds({ distribution: 'empirical', samples: [100, 200] }, 0.9), 0.2);
  assert.equal(thinkSeconds(null, 0.5), 0);
});
