// capability.mjs — the JMeter renderer's supports() contract (§4.3). Declared
// BEFORE rendering so the agent warns the human at VALIDATE about every §4
// construct JMeter only approximates. Per ISI-5656 the two headline JMeter
// approximations are:
//   * thinkTime.distribution=empirical  -> JSR223 timer sampling the pre-gen list
//   * correlates.extract.from=body_html -> Boundary Extractor best-effort
// plus the shared G-X1 note (non-http steps are topology/baseline, not driven).
//
// Everything else maps natively: open/closed arrival (Concurrency TG + Throughput
// Shaping Timer / Thread Group), weight, body_json/header/body_regex extraction,
// path/query/body/header injection, constant/uniform/gaussian/exponential timers,
// and Zipf cache pools via CSV Data Set Config.

import { makeCapabilityReport } from '../../renderer-kit/lib/renderer.mjs';
import { partitionDrivableSteps } from '../../renderer-kit/lib/model-access.mjs';

export function capabilityReport(model) {
  const spec = (model && model.spec) || {};
  const unsupported = [];

  const empiricalSteps = new Set();
  let hasBodyHtml = false;
  const undrivenTypes = new Set();

  for (const j of spec.journeys || []) {
    for (const s of j.steps || []) {
      if (s.thinkTime && s.thinkTime.distribution === 'empirical') empiricalSteps.add(s.id);
      for (const c of s.correlates || []) {
        if (c.extract && c.extract.from === 'body_html') hasBodyHtml = true;
      }
    }
    const { undriven } = partitionDrivableSteps(j);
    for (const s of undriven) undrivenTypes.add(s.callType);
  }

  if (empiricalSteps.size) {
    unsupported.push({
      feature: 'thinkTime.distribution=empirical',
      reason: 'JMeter has no native empirical-sample timer (only Constant/Uniform/Gaussian/Poisson)',
      approximation: 'JSR223 timer deterministically sampling the pre-generated empirical list',
    });
  }
  if (hasBodyHtml) {
    unsupported.push({
      feature: 'correlates.extract.from=body_html',
      reason: 'JMeter has no native HTML/DOM extractor',
      approximation: 'Boundary Extractor (left/right-boundary best-effort derived from the selector)',
    });
  }
  if (undrivenTypes.size) {
    unsupported.push({
      feature: `callType in {${[...undrivenTypes].sort().join(',')}}`,
      reason: 'renderers drive edge HTTP entrypoints only; grpc/db/mq/cache steps are topology/baseline',
      approximation: 'non-http steps are omitted from the .jmx (driven indirectly via the HTTP edge)',
    });
  }

  return makeCapabilityReport(unsupported);
}
