// renderer.mjs — the k6 renderer conformed to the formal Renderer interface
// (Renderer interface). The retrofit is "cosmetic" per §4.3: the existing
// `buildArtifacts()` already is a deterministic, network-free model->files function;
// this wraps it as { name, targetTool, schemaRange, supports(), render() } so the
// agent/registry can pick k6 the same way it picks jmeter/locust/gatling.
//
// render() does NOT run the V2a gate — that stays the SYNTHESIZE skill's on-disk
// gate (`synthesize()`), because V2a parses the script with `k6 inspect`/`node
// --check` and inspects files on disk. render() is the pure interchange surface.

import { defineRenderer, makeCapabilityReport } from './vendor/renderer.mjs';
import { loadModel, assertApproved } from './model.mjs';
import { buildArtifacts } from './synthesize.mjs';

/**
 * Capability report for k6. k6 is the reference target: it natively honors every
 * §4 construct (open+closed arrival, empirical think-time, body_html via regex,
 * full correlation), so a well-formed model yields an empty unsupported list.
 * The one honest caveat we surface: non-http steps (grpc/db/mq/cache) are
 * topology/baseline only and are not directly driven (G-X1) — same for every tool.
 */
function supports(model) {
  const spec = (model && model.spec) || {};
  const unsupported = [];
  const undrivenTypes = new Set();
  for (const j of spec.journeys || []) {
    for (const s of j.steps || []) {
      if (s.callType && s.callType !== 'http') undrivenTypes.add(s.callType);
    }
  }
  if (undrivenTypes.size) {
    unsupported.push({
      feature: `callType in {${[...undrivenTypes].sort().join(',')}}`,
      reason: 'renderers drive edge HTTP entrypoints only; grpc/db/mq/cache steps are topology/baseline',
      approximation: 'non-http steps are omitted from the k6 script (driven indirectly via the HTTP edge)',
    });
  }
  return makeCapabilityReport(unsupported);
}

/**
 * render(model, opts) -> { files, warnings }. Enforces the V1 approval gate (k6's
 * established fail-closed contract) then delegates to the shared in-memory builder.
 */
function render(modelPathOrObj, opts = {}) {
  const model = loadModel(modelPathOrObj);
  assertApproved(model); // V1 gate — k6 refuses unapproved models
  const { files, warnings } = buildArtifacts(model, opts);
  return { files, warnings };
}

export const k6Renderer = defineRenderer({
  name: 'k6',
  targetTool: 'Grafana k6',
  schemaRange: '>=1.0 <2.0',
  supports,
  render,
});
