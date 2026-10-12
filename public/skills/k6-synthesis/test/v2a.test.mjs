// Adversarial V2a tests — prove each check FAILS on a real violation, not just
// that it passes on good input (a checker that never fails is worthless).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { synthesize } from '../lib/synthesize.mjs';
import { v2aCheck } from '../lib/v2a.mjs';
import { loadModel } from '../lib/model.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');

function run(fn) {
  const out = mkdtempSync(path.join(tmpdir(), 'k6synth-v2a-'));
  try {
    return fn(out);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
}

function check(res, id) {
  return res.v2a.checks.find((c) => c.id === id);
}

test('baggage check fails when a request bypasses syntheticParams', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    // tamper: inject a raw request line that carries no synthetic baggage
    const tamperedSource = readFileSync(res.scriptPath, 'utf8') + '\nconst leak = http.get(url, {});\n';
    const tampered = v2aCheck({
      model: res.model,
      source: tamperedSource,
      scriptPath: res.scriptPath,
      outDir: out,
      options: res.options,
      maxRate: res.maxRate,
    });
    assert.equal(tampered.checks.find((c) => c.id === 'baggage').pass, false);
  });
});

test('caps check fails when declared rate exceeds caps.maxRps', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    const tampered = v2aCheck({
      model: res.model,
      source: readFileSync(res.scriptPath, 'utf8'),
      scriptPath: res.scriptPath,
      outDir: out,
      options: res.options,
      maxRate: 999, // over caps.maxRps (150)
    });
    assert.equal(tampered.checks.find((c) => c.id === 'caps').pass, false);
  });
});

test('ramp-down check fails when a ramping scenario does not end at 0', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    const badOptions = JSON.parse(JSON.stringify(res.options));
    const sc = Object.values(badOptions.scenarios).find((s) => String(s.executor).startsWith('ramping-'));
    sc.stages[sc.stages.length - 1].target = 50; // never cools down
    const tampered = v2aCheck({
      model: res.model,
      source: readFileSync(res.scriptPath, 'utf8'),
      scriptPath: res.scriptPath,
      outDir: out,
      options: badOptions,
      maxRate: res.maxRate,
    });
    assert.equal(tampered.checks.find((c) => c.id === 'rampdown').pass, false);
  });
});

test('pools check fails when a referenced pool JSON is missing', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    rmSync(path.join(out, 'payloads', 'productId.json'));
    const tampered = v2aCheck({
      model: res.model,
      source: readFileSync(res.scriptPath, 'utf8'),
      scriptPath: res.scriptPath,
      outDir: out,
      options: res.options,
      maxRate: res.maxRate,
    });
    assert.equal(tampered.checks.find((c) => c.id === 'pools').pass, false);
  });
});

test('correlation check fails when a dependsOn step lacks a fail-fast guard', () => {
  run((out) => {
    const res = synthesize(FIXTURE, out);
    // source with the guard stripped
    const stripped = readFileSync(res.scriptPath, 'utf8').replace(/broken chain at step=place-order:/g, "x");
    const tampered = v2aCheck({
      model: res.model,
      source: stripped,
      scriptPath: res.scriptPath,
      outDir: out,
      options: res.options,
      maxRate: res.maxRate,
    });
    assert.equal(tampered.checks.find((c) => c.id === 'correlation').pass, false);
  });
});
