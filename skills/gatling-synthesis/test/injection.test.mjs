// injection.mjs unit tests — arrivalProfile -> Gatling injection (G3, G-D1).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildInjection, scalaDuration } from '../lib/injection.mjs';

test('scalaDuration maps model units to Gatling durations', () => {
  assert.equal(scalaDuration('5m'), '5.minutes');
  assert.equal(scalaDuration('30s'), '30.seconds');
  assert.equal(scalaDuration('500ms'), '500.milliseconds');
  assert.equal(scalaDuration('1h'), '1.hours');
});

test('open model: steady -> constantUsersPerSec, ramp -> rampUsersPerSec from prev', () => {
  const inj = buildInjection({
    model: 'open',
    stages: [
      { duration: '5m', rate: 100, shape: 'ramp_up' },
      { duration: '10m', rate: 100, shape: 'plateau' },
      { duration: '5m', rate: 0, shape: 'ramp_down' },
    ],
  });
  assert.equal(inj.model, 'open');
  assert.equal(inj.peakRate, 100);
  assert.deepEqual(inj.steps, [
    'rampUsersPerSec(0.0).to(100.0).during(5.minutes)',
    'constantUsersPerSec(100.0).during(10.minutes)',
    'rampUsersPerSec(100.0).to(0.0).during(5.minutes)',
  ]);
});

test('closed model: constant/ramp concurrent users + Little-Law ceiling', () => {
  const inj = buildInjection({
    model: 'closed',
    stages: [
      { duration: '2m', rate: 10, shape: 'ramp_up' },
      { duration: '8m', rate: 10, shape: 'steady' },
      { duration: '2m', rate: 0, shape: 'ramp_down' },
    ],
    littlesLawCheck: { expectedConcurrency: 12 },
  });
  assert.equal(inj.model, 'closed');
  assert.equal(inj.maxConcurrent, 12);
  assert.deepEqual(inj.steps, [
    'rampConcurrentUsers(0).to(10).during(2.minutes)',
    'constantConcurrentUsers(10).during(8.minutes)',
    'rampConcurrentUsers(10).to(0).during(2.minutes)',
  ]);
});

test('ramp-down to 0 is synthesized when a ramping profile ends above zero', () => {
  const inj = buildInjection({
    model: 'open',
    stages: [{ duration: '5m', rate: 50, shape: 'ramp_up' }],
  });
  assert.equal(inj.steps.length, 2);
  assert.match(inj.steps[1], /rampUsersPerSec\(50\.0\)\.to\(0\.0\)\.during\(5\.minutes\)/);
  assert.ok(inj.warnings.some((w) => /ramp-down to 0 synthesized/.test(w)));
});

test('a single steady open stage needs no ramp-down', () => {
  const inj = buildInjection({
    model: 'open',
    stages: [{ duration: '179m', rate: 0.7365, shape: 'steady' }],
  });
  assert.deepEqual(inj.steps, ['constantUsersPerSec(0.7365).during(179.minutes)']);
  assert.equal(inj.warnings.length, 0);
});
