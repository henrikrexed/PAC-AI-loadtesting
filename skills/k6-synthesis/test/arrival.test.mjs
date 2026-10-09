import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildScenario, enforceRampDown, durationToSeconds } from '../lib/arrival.mjs';

const RAMP = {
  model: 'open',
  stages: [
    { duration: '5m', rate: 100, shape: 'ramp_up' },
    { duration: '10m', rate: 100, shape: 'plateau' },
    { duration: '5m', rate: 0, shape: 'ramp_down' },
  ],
};

test('durationToSeconds parses all units', () => {
  assert.equal(durationToSeconds('500ms'), 0.5);
  assert.equal(durationToSeconds('30s'), 30);
  assert.equal(durationToSeconds('5m'), 300);
  assert.equal(durationToSeconds('1h'), 3600);
  assert.throws(() => durationToSeconds('5x'));
});

test('enforceRampDown appends a zero stage only when missing', () => {
  assert.equal(enforceRampDown(RAMP.stages).appended, false);
  const noDown = { stages: [{ duration: '5m', rate: 100, shape: 'ramp_up' }] };
  const r = enforceRampDown(noDown.stages);
  assert.equal(r.appended, true);
  assert.equal(r.stages[r.stages.length - 1].rate, 0);
});

test('open ramping scenario scales rate by weight and ends at 0 (G3)', () => {
  const { scenario, maxRate } = buildScenario('checkout', RAMP, 0.4, { concurrency: 10, caps: { maxVus: 120 } });
  assert.equal(scenario.executor, 'ramping-arrival-rate');
  assert.equal(scenario.startRate, 0);
  assert.equal(scenario.stages[0].target, 40); // 100 * 0.4
  assert.equal(scenario.stages[scenario.stages.length - 1].target, 0);
  assert.equal(maxRate, 40);
  assert.ok(scenario.maxVUs <= 120);
});

test('single steady stage -> constant-arrival-rate (open)', () => {
  const steady = { model: 'open', stages: [{ duration: '10m', rate: 50, shape: 'steady' }] };
  const { scenario } = buildScenario('browse', steady, 1, {});
  assert.equal(scenario.executor, 'constant-arrival-rate');
  assert.equal(scenario.rate, 50);
});

test('closed model -> ramping-vus with rounded integer targets', () => {
  const { scenario } = buildScenario('seatbound', { model: 'closed', stages: RAMP.stages }, 0.5, { concurrency: 8 });
  assert.equal(scenario.executor, 'ramping-vus');
  assert.equal(scenario.startVUs, 0);
  assert.equal(scenario.stages[scenario.stages.length - 1].target, 0);
});

test('VU ceiling clamps to caps.maxVus with a warning', () => {
  const { scenario, warnings } = buildScenario('big', RAMP, 1, { concurrency: 1000, caps: { maxVus: 120 } });
  assert.equal(scenario.maxVUs, 120);
  assert.ok(warnings.some((w) => w.includes('clamped')));
});
