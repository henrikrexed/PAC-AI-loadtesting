// renderer.mjs — the JMeter renderer conformed to the formal Renderer interface
// (research §4.3, ISI-5655). A drop-in against the same registry + acceptance
// harness as k6/locust/gatling: model-in -> { files, warnings }, deterministic,
// no network.
//
// render() enforces the V1 approval gate (the common-contract input is an
// APPROVED model) then delegates to the shared in-memory builder so render()
// files[] are byte-identical to what synthesize() writes to disk. The own static
// check (check.mjs) stays in synthesize() — the on-disk gate — not in render(),
// mirroring k6 (render() is the pure interchange surface).

import { defineRenderer } from '../../renderer-kit/lib/renderer.mjs';
import { loadModel, assertApproved } from './model.mjs';
import { buildArtifacts } from './synthesize.mjs';
import { capabilityReport } from './capability.mjs';

function supports(model) {
  return capabilityReport(model);
}

function render(modelPathOrObj, _opts = {}) {
  const model = loadModel(modelPathOrObj);
  assertApproved(model); // V1 gate — refuse unapproved models
  const { files, warnings } = buildArtifacts(model);
  return { files, warnings };
}

export const jmeterRenderer = defineRenderer({
  name: 'jmeter',
  targetTool: 'Apache JMeter',
  schemaRange: '>=1.0 <2.0',
  supports,
  render,
});
