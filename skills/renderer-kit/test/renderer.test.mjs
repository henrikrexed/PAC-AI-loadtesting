// Interface + capability-report + render-result shape validation.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  makeCapabilityReport,
  validateCapabilityReport,
  validateRenderResult,
  validateRenderer,
  defineRenderer,
} from '../lib/renderer.mjs';

test('makeCapabilityReport derives ok from the unsupported list', () => {
  assert.deepEqual(makeCapabilityReport([]), { ok: true, unsupported: [] });
  const r = makeCapabilityReport([{ feature: 'x', reason: 'y' }]);
  assert.equal(r.ok, false);
  assert.equal(r.unsupported.length, 1);
});

test('validateCapabilityReport accepts a well-formed report', () => {
  assert.doesNotThrow(() => validateCapabilityReport(makeCapabilityReport([])));
  assert.doesNotThrow(() =>
    validateCapabilityReport(makeCapabilityReport([{ feature: 'f', reason: 'r', approximation: 'a' }]))
  );
});

test('validateCapabilityReport rejects malformed reports', () => {
  assert.throws(() => validateCapabilityReport(null), TypeError);
  assert.throws(() => validateCapabilityReport({ ok: 'yes', unsupported: [] }), TypeError);
  assert.throws(() => validateCapabilityReport({ ok: true, unsupported: 'no' }), TypeError);
  // ok/unsupported inconsistency
  assert.throws(() => validateCapabilityReport({ ok: true, unsupported: [{ feature: 'f', reason: 'r' }] }), TypeError);
  // missing feature/reason
  assert.throws(() => validateCapabilityReport({ ok: false, unsupported: [{ feature: 'f' }] }), TypeError);
  // approximation wrong type
  assert.throws(
    () => validateCapabilityReport({ ok: false, unsupported: [{ feature: 'f', reason: 'r', approximation: 7 }] }),
    TypeError
  );
});

test('validateRenderResult requires at least one well-formed file and a warnings array', () => {
  assert.doesNotThrow(() => validateRenderResult({ files: [{ path: 'a.js', content: '' }], warnings: [] }));
  assert.throws(() => validateRenderResult({ files: [], warnings: [] }), TypeError);
  assert.throws(() => validateRenderResult({ files: [{ path: '', content: '' }], warnings: [] }), TypeError);
  assert.throws(() => validateRenderResult({ files: [{ path: 'a', content: 1 }], warnings: [] }), TypeError);
  assert.throws(() => validateRenderResult({ files: [{ path: 'a', content: '' }] }), TypeError);
});

test('validateRenderer enforces the static interface shape', () => {
  const ok = { name: 'x', targetTool: 'X', schemaRange: '>=1.0', supports() {}, render() {} };
  assert.doesNotThrow(() => validateRenderer(ok));
  assert.throws(() => validateRenderer({ ...ok, name: '' }), TypeError);
  assert.throws(() => validateRenderer({ ...ok, supports: 'no' }), TypeError);
  assert.throws(() => validateRenderer(null), TypeError);
});

test('defineRenderer fills defaults and freezes', () => {
  const r = defineRenderer({ name: 'k', supports: () => makeCapabilityReport([]), render: () => ({ files: [], warnings: [] }) });
  assert.equal(r.targetTool, 'k');
  assert.equal(r.schemaRange, '>=1.0 <2.0');
  assert.ok(Object.isFrozen(r));
});
