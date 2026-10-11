// renderer.mjs — the Locust renderer conformed to the formal Renderer interface
// (research §4.3, ISI-5655 foundation). This is the production Locust renderer
// that replaces the renderer-kit `locust-stub`: model-in -> { files, warnings }.
//
// supports() declares EVERY feature Locust approximates/omits so the agent warns
// the human at VALIDATE (§4.3): open arrival (Locust is closed-native, G-O1),
// empirical think-time (G-E1), body_html extraction (G-E1), and non-http steps
// (G-X1). render() is the pure interchange surface — deterministic, no network —
// delegating to the shared in-memory builder so render() files == what
// synthesize() writes to disk byte-for-byte.
//
// render() does NOT hard-gate on approval: it emits an unapproved model for human
// PREVIEW (with a prominent warning), because the hard V1 gate is the SYNTHESIZE/
// EXECUTE boundary, not the interchange surface. The static check (v2a) reports
// approval status via its advisory `approved` flag.

import { defineRenderer, makeCapabilityReport } from '../../renderer-kit/lib/renderer.mjs';
import { partitionDrivableSteps } from '../../renderer-kit/lib/model-access.mjs';
import { buildArtifacts } from './synthesize.mjs';

function supports(model) {
  const spec = (model && model.spec) || {};
  const unsupported = [];

  // G-O1: open arrival — Locust is user/closed-native; needs LoadTestShape + pacing.
  if (spec.arrivalProfile && spec.arrivalProfile.model === 'open') {
    unsupported.push({
      feature: 'arrivalProfile.model=open',
      reason: 'Locust is user/closed-native (concurrent users, not an arrival rate)',
      approximation: 'LoadTestShape + per-task constant_pacing to approximate target iterations/s (Little\'s Law)',
    });
  }

  const seenEmpirical = new Set();
  let hasBodyHtml = false;
  const undrivenTypes = new Set();
  for (const j of spec.journeys || []) {
    for (const s of j.steps || []) {
      if (s.thinkTime && s.thinkTime.distribution === 'empirical') seenEmpirical.add(s.id);
      for (const c of s.correlates || []) {
        if (c.extract && c.extract.from === 'body_html') hasBodyHtml = true;
      }
    }
    const { undriven } = partitionDrivableSteps(j);
    for (const s of undriven) undrivenTypes.add(s.callType);
  }

  if (seenEmpirical.size) {
    unsupported.push({
      feature: 'thinkTime.distribution=empirical',
      reason: 'Locust wait_time has no native empirical-sample distribution',
      approximation: 'custom think_seconds() sampling from the pre-generated empirical list (think.py)',
    });
  }
  if (hasBodyHtml) {
    unsupported.push({
      feature: 'correlates.extract.from=body_html',
      reason: 'Locust has no native HTML extractor',
      approximation: 'marker / regex extraction in the task body (chain.py)',
    });
  }
  if (undrivenTypes.size) {
    unsupported.push({
      feature: `callType in {${[...undrivenTypes].sort().join(',')}}`,
      reason: 'renderers drive edge HTTP entrypoints only; grpc/db/mq/cache steps are topology/baseline',
      approximation: 'non-http steps are omitted from the locustfile (driven indirectly via the HTTP edge)',
    });
  }

  return makeCapabilityReport(unsupported);
}

function render(model, opts = {}) {
  const report = supports(model);
  const { files, warnings } = buildArtifacts(model, opts);
  const out = [...warnings];
  // surface the declared approximations as VALIDATE warnings (parity with the stub)
  for (const u of report.unsupported) {
    out.push(`locust: ${u.feature} — ${u.reason}${u.approximation ? ` (approx: ${u.approximation})` : ''}`);
  }
  const a = model && model.status && model.status.approval;
  const approved = !!a && a.decision === 'approved' && a.revision === model.status.revision;
  if (!approved) {
    out.push('locust: model is NOT approved for its current revision — rendered for PREVIEW only; the V1 gate blocks EXECUTE until approved');
  }
  return { files, warnings: out };
}

export const locustRenderer = defineRenderer({
  name: 'locust',
  targetTool: 'Locust',
  schemaRange: '>=1.0 <2.0',
  supports,
  render,
});
