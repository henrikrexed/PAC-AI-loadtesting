// acceptance.mjs — the SHARED renderer acceptance harness (vendored from renderer-kit).
//
// Every renderer's test suite calls `assertRendererConformance(renderer, model)`
// so all four tools (k6/jmeter/locust/gatling) are held to the same bar:
//   1. the object conforms to the Renderer interface (static shape),
//   2. supports() returns a well-formed capability report,
//   3. render() returns a well-formed { files, warnings },
//   4. render() is DETERMINISTIC — rendering the same model twice is byte-identical
//      (the §4.3 "pure function, no network" guarantee, mechanically enforced),
//   5. file paths are unique and relative (no leading "/" or "..").
//
// This is intentionally test-framework-agnostic: it throws on any violation (so it
// works under node:test, vitest, jest, or a bare script) and otherwise returns the
// gathered evidence for the caller to make further tool-specific assertions.

import assert from 'node:assert/strict';
import {
  validateRenderer,
  validateCapabilityReport,
  validateRenderResult,
} from '../../lib/vendor/renderer.mjs';

/** Stable key for a file list so two renders can be compared byte-for-byte. */
function serializeFiles(files) {
  return [...files]
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0))
    .map((f) => `>>> ${f.path}\n${f.content}`)
    .join('\n');
}

/**
 * Run the full shared acceptance convention against one renderer + model.
 * Returns { supports, render, serialized } on success; throws on any violation.
 */
export function assertRendererConformance(renderer, model, opts = {}) {
  const who = (renderer && renderer.name) || 'renderer';

  // 1. interface shape
  validateRenderer(renderer);

  // 2. capability report shape (the supports() convention)
  const support = renderer.supports(model);
  validateCapabilityReport(support, who);

  // 3. render result shape
  const first = renderer.render(model, opts);
  validateRenderResult(first, who);

  // 4. determinism — render again and compare byte-for-byte
  const second = renderer.render(model, opts);
  validateRenderResult(second, who);
  const s1 = serializeFiles(first.files);
  const s2 = serializeFiles(second.files);
  assert.equal(s1, s2, `${who}.render() is not deterministic: two renders of the same model differ`);

  // 5. paths are unique and relative
  const seen = new Set();
  for (const f of first.files) {
    assert.ok(!f.path.startsWith('/'), `${who}.render() produced an absolute path: ${f.path}`);
    assert.ok(!f.path.split('/').includes('..'), `${who}.render() produced a traversing path: ${f.path}`);
    assert.ok(!seen.has(f.path), `${who}.render() produced a duplicate path: ${f.path}`);
    seen.add(f.path);
  }

  return { supports: support, render: first, serialized: s1 };
}

/**
 * Golden-fixture determinism check: assert a renderer reproduces a previously
 * captured serialization byte-for-byte. Pass `golden === null` to capture (returns
 * the current serialization so the caller can write/update the golden file).
 */
export function assertGolden(renderer, model, golden, opts = {}) {
  const current = serializeFiles(renderer.render(model, opts).files);
  if (golden != null) {
    assert.equal(current, golden, `${renderer.name}: rendered output drifted from the golden fixture`);
  }
  return current;
}
