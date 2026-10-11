// capabilities.mjs — the honest capability report for the Gatling renderer.
//
// Declared BEFORE rendering (research §4.3) so the agent warns the human at VALIDATE
// about every §4 construct Gatling cannot natively honor. Shared by renderer.supports()
// and render() (whose warnings mirror the report) so the two never drift.
//
// Gatling NATIVELY honors: open+closed injection (G3), jsonPath/header/headerRegex/
// regex correlation (G2), uniform + constant pauses, JSON feeders (G4), and the
// synthetic=true baggage header. The approximations it must declare:
//   - empirical think-time (no native sampled-distribution pause)  [issue-mandated]
//   - exponential think-time (no native per-step exponential pause)
//   - body_html extraction (no native HTML-DOM extractor -> regex)
//   - non-http callType steps (grpc/db/mq/cache are topology/baseline only — G-X1)

export function collectUnsupported(model) {
  const spec = (model && model.spec) || {};
  const unsupported = [];
  const thinkDists = new Set();
  let hasBodyHtml = false;
  const undrivenTypes = new Set();

  for (const j of spec.journeys || []) {
    for (const s of j.steps || []) {
      if (s.thinkTime && s.thinkTime.distribution) thinkDists.add(s.thinkTime.distribution);
      if (s.callType && s.callType !== 'http') undrivenTypes.add(s.callType);
      for (const c of s.correlates || []) {
        if (c.extract && c.extract.from === 'body_html') hasBodyHtml = true;
      }
    }
  }

  if (thinkDists.has('empirical')) {
    unsupported.push({
      feature: 'thinkTime.distribution=empirical',
      reason: 'Gatling has no native empirical/sampled-distribution pause',
      approximation: 'fixed mean pause (feed an empirical sample via a feeder to randomize)',
    });
  }
  if (thinkDists.has('exponential')) {
    unsupported.push({
      feature: 'thinkTime.distribution=exponential',
      reason: 'Gatling per-step exponential pauses are not native (exponentialPauses is a global pause-type)',
      approximation: 'fixed mean pause; set the simulation-global .exponentialPauses to randomize all single-value pauses',
    });
  }
  if (hasBodyHtml) {
    unsupported.push({
      feature: 'correlates.extract.from=body_html',
      reason: 'Gatling has no native HTML-DOM extractor',
      approximation: 'regex over the raw response body',
    });
  }
  if (undrivenTypes.size) {
    unsupported.push({
      feature: `callType in {${[...undrivenTypes].sort().join(',')}}`,
      reason: 'renderers drive edge HTTP entrypoints only; grpc/db/mq/cache steps are topology/baseline',
      approximation: 'non-http steps are omitted from the simulation (driven indirectly via the HTTP edge)',
    });
  }
  return unsupported;
}
