import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  zipfWeights,
  expectedHitRatio,
  fitAlpha,
  sizePool,
  generatePool,
  simulateHitRatio,
} from '../lib/payloads.mjs';

test('zipfWeights normalize to 1 and are monotone decreasing', () => {
  const w = zipfWeights(100, 1.0);
  const sum = w.reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 1) < 1e-9);
  for (let i = 1; i < w.length; i++) assert.ok(w[i] <= w[i - 1]);
});

test('expectedHitRatio is monotone increasing in alpha', () => {
  const K = 2000;
  const W = 2400;
  const h0 = expectedHitRatio(K, 0, W);
  const h1 = expectedHitRatio(K, 1, W);
  const h2 = expectedHitRatio(K, 2, W);
  assert.ok(h0 < h1 && h1 < h2);
});

test('sizePool math follows the §3.3 rule', () => {
  assert.equal(sizePool({ R: 40, T: 60, missRatio: 0.2, mode: 'ttl-miss' }), 480);
  assert.equal(sizePool({ R: 40, T: 60, mode: 'ttl-unique' }), 2400);
  assert.equal(sizePool({ R: 40, D: 1200, mode: 'run-unique' }), 48000);
});

test('fitAlpha reproduces a target hit ratio analytically', () => {
  const K = 2000;
  const W = 2400;
  const { alpha, achieved, clamped } = fitAlpha(K, W, 0.8);
  assert.equal(clamped, false);
  assert.ok(Math.abs(achieved - 0.8) < 1e-3, `achieved=${achieved}`);
  assert.ok(alpha > 0);
});

test('AC3: cache-key pool reproduces target hit ratio within model tolerance (0.10)', () => {
  const spec = { fields: [{ name: 'id', type: 'string', generator: 'sequence' }], seed: 1337, cacheProfile: { targetHitRatio: 0.8, keyCardinality: 2000, backingStoreSeeded: true } };
  const pool = generatePool('productId', spec, { ratePerSec: 40, ttlSec: 60, durationSec: 1200 });
  assert.equal(pool.kind, 'cache-key');
  assert.equal(pool.keys.length, 2000);
  assert.equal(pool.cdf.length, 2000);
  assert.equal(pool.cacheProfile.withinTolerance, true);
  assert.ok(Math.abs(pool.cacheProfile.achievedHitRatio - 0.8) <= 0.1);

  // Monte-Carlo: actual Zipf draws through the generated CDF reproduce the ratio
  const W = pool.cacheProfile.window;
  const achieved = simulateHitRatio({ cdf: pool.cdf, W, N: W * 10, seed: 99 });
  assert.ok(Math.abs(achieved - 0.8) <= 0.1, `simulated hit ratio ${achieved}`);
});

test('generatePool is deterministic given the seed', () => {
  const spec = { fields: [{ name: 'email', type: 'string', generator: 'faker:email' }], seed: 7, count: 20 };
  const a = generatePool('checkout', spec, {});
  const b = generatePool('checkout', spec, {});
  assert.deepEqual(a.records, b.records);
});

test('record pool is PII-free by construction', () => {
  const spec = { fields: [{ name: 'email', type: 'string', generator: 'faker:email' }, { name: 'currency', type: 'enum', values: ['USD', 'EUR'] }], seed: 7, count: 10 };
  const pool = generatePool('checkout', spec, {});
  assert.equal(pool.kind, 'record');
  for (const rec of pool.records) {
    assert.ok(String(rec.email).endsWith('@synthetic.invalid'));
    assert.ok(['USD', 'EUR'].includes(rec.currency));
  }
});

test('honouring a pinned alpha records the resulting (possibly off-target) ratio', () => {
  const spec = { fields: [{ name: 'id', type: 'string' }], seed: 1, cacheProfile: { targetHitRatio: 0.95, keyCardinality: 2000, distributionAlpha: 0 } };
  const pool = generatePool('x', spec, { ratePerSec: 40, ttlSec: 60 });
  assert.equal(pool.cacheProfile.distributionAlpha, 0);
  // uniform alpha=0 under-delivers vs 0.95 target -> flagged out of tolerance
  assert.equal(pool.cacheProfile.withinTolerance, false);
});
