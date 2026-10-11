// index.mjs — public surface of renderer-kit (the renderer foundation, ISI-5655).
export {
  makeCapabilityReport,
  validateCapabilityReport,
  validateRenderResult,
  validateRenderer,
  defineRenderer,
} from './renderer.mjs';
export { RendererRegistry, createRegistry } from './registry.mjs';
export { assertRendererConformance, assertGolden } from './acceptance.mjs';
export {
  parseOperation,
  resolveRequest,
  methodHasBody,
  resolveFieldTarget,
  partitionDrivableSteps,
} from './model-access.mjs';
export { locustStub } from './renderers/locust-stub.mjs';
