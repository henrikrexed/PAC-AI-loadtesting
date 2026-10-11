// index.mjs — public surface of gatling-synthesis (the Gatling renderer, ISI-5658).
export { gatlingRenderer } from './renderer.mjs';
export { buildSimulation } from './simulation.mjs';
export { buildInjection, scalaDuration } from './injection.mjs';
export { buildFeeder } from './feeders.mjs';
export { planCorrelations, extractCheck, toJsonPath, canonHeader, saveKey } from './chain.mjs';
export { collectUnsupported } from './capabilities.mjs';
export { lintSimulation } from './lint.mjs';
