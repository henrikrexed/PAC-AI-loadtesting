// renderer.mjs — the Gatling renderer conformed to the formal Renderer interface
// (research §4.3, ISI-5655). Like the locust-stub and unlike k6's on-disk
// `synthesize()` wrapper, render() is the PURE interchange surface: no network, no
// disk, no V1 approval gate (approval is the host's VALIDATE gate before calling
// render — mirrors how the acceptance fixtures include an unapproved real model).
//
// The renderer's OWN static check (V2a-equivalent) is `lintSimulation` — run it on
// the render result before EXECUTE; full scalac/gatling compilation is EXECUTE-time.

import { defineRenderer, makeCapabilityReport } from '../../renderer-kit/lib/renderer.mjs';
import { collectUnsupported } from './capabilities.mjs';
import { buildSimulation } from './simulation.mjs';

function supports(model) {
  return makeCapabilityReport(collectUnsupported(model));
}

function render(model, opts = {}) {
  const { files, warnings } = buildSimulation(model, opts);
  return { files, warnings };
}

export const gatlingRenderer = defineRenderer({
  name: 'gatling',
  targetTool: 'Gatling',
  schemaRange: '>=1.0 <2.0',
  supports,
  render,
});
