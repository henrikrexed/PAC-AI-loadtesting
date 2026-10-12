// Acceptance tests — the ISI-5656 acceptance criteria, end-to-end, on BOTH the
// shop-checkout fixture and the real otel-astronomy-frontend model.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { synthesize } from '../lib/synthesize.mjs';
import { loadModel } from '../lib/model.mjs';
import { checkWellFormed } from '../lib/check.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const REAL = path.join(HERE, '..', '..', '..', 'loadtests', 'otel-astronomy-frontend', 'workload-model.json');

function run(fn) {
  const out = mkdtempSync(path.join(tmpdir(), 'jmetersynth-'));
  try {
    return fn(out);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
}

function approvedReal() {
  const m = loadModel(REAL);
  m.status.approval = { revision: m.status.revision, decision: 'approved', decisionBy: 't', decisionAt: '2026-10-11T00:00:00Z' };
  return m;
}

test('AC: renders shop-checkout AND the real model; both pass the own static check', () => {
  run((out) => {
    const r1 = synthesize(FIXTURE, out);
    for (const c of r1.check.checks) assert.ok(c.pass, `shop-checkout ${c.title}: ${c.detail}`);
    assert.equal(r1.check.pass, true);
  });
  run((out) => {
    const r2 = synthesize(approvedReal(), out);
    for (const c of r2.check.checks) assert.ok(c.pass, `astronomy ${c.title}: ${c.detail}`);
    assert.equal(r2.check.pass, true);
  });
});

test('AC: produced .jmx is well-formed XML with balanced hashTrees', () => {
  run((out) => {
    const r = synthesize(FIXTURE, out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'shop-checkout.jmx'), 'utf8');
    assert.equal(checkWellFormed(jmx).ok, true);
    const open = (jmx.match(/<hashTree>/g) || []).length;
    const close = (jmx.match(/<\/hashTree>/g) || []).length;
    assert.equal(open, close);
  });
});

test('AC: request chaining — step N consumes an id extracted from step N-1', () => {
  run((out) => {
    const r = synthesize(FIXTURE, out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'shop-checkout.jmx'), 'utf8');
    // view-product extracts id (JSON) -> add-to-cart body references it
    // (step ids are sanitized for JMeter var names: "view-product" -> "view_product")
    assert.match(jmx, /JSONPostProcessor\.referenceNames">corr__view_product__id</);
    assert.match(jmx, /\$\{corr__view_product__id\}/);
    // add-to-cart extracts cartId -> place-order body references it
    assert.match(jmx, /JSONPostProcessor\.referenceNames">corr__add_to_cart__cartId</);
    assert.match(jmx, /\$\{corr__add_to_cart__cartId\}/);
  });
});

test('AC: real-model chaining uses a header Regex Extractor (set-cookie:session -> cookie)', () => {
  run((out) => {
    synthesize(approvedReal(), out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'otel-astronomy-frontend.jmx'), 'utf8');
    assert.match(jmx, /RegexExtractor\.useHeaders">true/);
    assert.match(jmx, /session=\(\[\^;\\s\]\+\)/);
    assert.match(jmx, /\$\{corr__s2__set_cookie_session\}/);
  });
});

test('AC: synthetic=true is stamped on traffic via a baggage Header Manager', () => {
  run((out) => {
    const r = synthesize(FIXTURE, out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'shop-checkout.jmx'), 'utf8');
    assert.match(jmx, /Header\.name">baggage<\/stringProp>/);
    assert.match(jmx, /Header\.value">synthetic=true<\/stringProp>/);
    assert.equal(r.check.checks.find((c) => c.id === 'synthetic').pass, true);
  });
});

test('AC: cache-avoidance Zipf pool -> CSV Data Set Config', () => {
  run((out) => {
    synthesize(FIXTURE, out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'shop-checkout.jmx'), 'utf8');
    assert.match(jmx, /<CSVDataSet\b/);
    assert.match(jmx, /filename">data\/productId\.csv</);
    const csv = readFileSync(path.join(out, 'jmeter', 'data', 'productId.csv'), 'utf8');
    const rows = csv.trim().split('\n');
    assert.equal(rows[0], 'id'); // header
    assert.ok(rows.length > 100); // materialized zipf sample
  });
});

test('AC: open arrival -> Concurrency Thread Group + Throughput Shaping Timer', () => {
  run((out) => {
    const r = synthesize(FIXTURE, out);
    const jmx = readFileSync(path.join(out, 'jmeter', 'shop-checkout.jmx'), 'utf8');
    assert.match(jmx, /ConcurrencyThreadGroup\b/);
    assert.match(jmx, /VariableThroughputTimer\b/);
    assert.ok(r.meta.isOpen);
  });
});

test('V1 gate: synthesize refuses an unapproved model', () => {
  const m = loadModel(FIXTURE);
  m.status.revision = 4; // invalidate approval
  run((out) => assert.throws(() => synthesize(m, out), /V1 gate/));
});
