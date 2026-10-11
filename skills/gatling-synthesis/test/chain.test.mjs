// chain.mjs unit tests — correlation extraction + injection planning (G2).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toJsonPath, canonHeader, extractCheck, planCorrelations, saveKey } from '../lib/chain.mjs';

test('toJsonPath normalizes to a $-rooted JsonPath', () => {
  assert.equal(toJsonPath('id'), '$.id');
  assert.equal(toJsonPath('products[0].id'), '$.products[0].id');
  assert.equal(toJsonPath('$.id'), '$.id');
  assert.equal(toJsonPath('[0].id'), '$[0].id');
});

test('canonHeader canonicalizes header casing', () => {
  assert.equal(canonHeader('set-cookie'), 'Set-Cookie');
  assert.equal(canonHeader('cookie'), 'Cookie');
  assert.equal(canonHeader('X-Request-ID'), 'X-Request-Id');
});

test('extractCheck renders a Gatling check per extract.from', () => {
  assert.equal(extractCheck({ from: 'body_json', path: '$.id' }, 'k'), 'jsonPath("$.id").saveAs("k")');
  assert.equal(extractCheck({ from: 'header', path: 'Location' }, 'k'), 'header("Location").saveAs("k")');
  assert.equal(
    extractCheck({ from: 'header', path: 'set-cookie:session' }, 'k'),
    'headerRegex("Set-Cookie", "session=([^;]+)").saveAs("k")'
  );
  assert.equal(extractCheck({ from: 'regex', path: 'id=(\\d+)' }, 'k'), 'regex("id=(\\\\d+)").saveAs("k")');
});

test('extractCheck records body_html as an approximation', () => {
  const approx = [];
  const check = extractCheck({ from: 'body_html', path: '#token' }, 'k', approx);
  assert.match(check, /^regex\(/);
  assert.ok(approx.some((a) => a.feature === 'correlates.extract.from=body_html'));
});

test('planCorrelations attaches saveAs to the SOURCE and injects at the consumer', () => {
  const journey = {
    steps: [
      { id: 's1', operation: 'GET /a' },
      {
        id: 's2',
        operation: 'POST /b',
        correlates: [
          { sourceStepId: 's1', extract: { from: 'body_json', path: 'id' }, inject: { into: 'body_field', as: 'productId' } },
        ],
      },
    ],
  };
  const { savesByStep, injectsByStep } = planCorrelations(journey);
  const key = saveKey('s2', 'productId');
  assert.deepEqual(savesByStep.s1, [`jsonPath("$.id").saveAs("${key}")`]);
  assert.deepEqual(injectsByStep.s2, [{ into: 'body_field', as: 'productId', key }]);
});

test('one source feeding two consumers yields two independent saves', () => {
  const journey = {
    steps: [
      { id: 's2', operation: 'POST /cart' },
      { id: 's3', operation: 'GET /cart', correlates: [{ sourceStepId: 's2', extract: { from: 'header', path: 'set-cookie:session' }, inject: { into: 'header', as: 'cookie' } }] },
      { id: 's4', operation: 'POST /checkout', correlates: [{ sourceStepId: 's2', extract: { from: 'header', path: 'set-cookie:session' }, inject: { into: 'header', as: 'cookie' } }] },
    ],
  };
  const { savesByStep } = planCorrelations(journey);
  assert.equal(savesByStep.s2.length, 2);
  assert.ok(savesByStep.s2.some((c) => c.includes('c_s3_cookie')));
  assert.ok(savesByStep.s2.some((c) => c.includes('c_s4_cookie')));
});
