// model.mjs — load an approved workload model and gate on the V1 approval.
// SYNTHESIZE refuses to run on a model that is not approved for its current
// revision (methodology §3.2 rule 2, §6 invariant: V1 is hash/revision-bound).

import { readFileSync } from 'node:fs';

export function loadModel(pathOrObj) {
  const model = typeof pathOrObj === 'string' ? JSON.parse(readFileSync(pathOrObj, 'utf8')) : pathOrObj;
  assertStructure(model);
  return model;
}

function assertStructure(model) {
  if (!model || model.kind !== 'WorkloadModel') throw new Error('not a WorkloadModel');
  if (!model.spec || !Array.isArray(model.spec.journeys) || model.spec.journeys.length === 0) {
    throw new Error('model has no journeys');
  }
  if (!model.spec.arrivalProfile || !Array.isArray(model.spec.arrivalProfile.stages)) {
    throw new Error('model has no arrivalProfile.stages');
  }
  if (!model.status || typeof model.status.revision !== 'number') {
    throw new Error('model has no status.revision');
  }
}

/**
 * Enforce the V1 human gate. Throws unless status.approval exists, decision is
 * "approved", and the approved revision matches the current model revision.
 */
export function assertApproved(model) {
  const a = model.status && model.status.approval;
  if (!a) throw new Error('V1 gate: model has no status.approval — refuse to synthesize');
  if (a.decision !== 'approved') {
    throw new Error(`V1 gate: approval.decision="${a.decision}" (need "approved") — refuse to synthesize`);
  }
  if (a.revision !== model.status.revision) {
    throw new Error(
      `V1 gate: approval is for revision ${a.revision} but model is revision ${model.status.revision} — approval invalidated, re-validate`
    );
  }
  return a;
}

/** Map each referenced payload pool to its kind ('cache-key' | 'record'). */
export function poolKinds(model) {
  const pools = (model.spec && model.spec.payloads) || {};
  const kinds = {};
  for (const [id, spec] of Object.entries(pools)) {
    kinds[id] = spec.cacheProfile ? 'cache-key' : 'record';
  }
  return kinds;
}
