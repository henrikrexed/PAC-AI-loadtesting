// model-access.mjs — tool-agnostic accessors over the §4 workload model.
//
// These encapsulate the §4 v1.1 additive fields (G-R1 steps[].request, G-P1
// fields[].target) with a back-compat fallback, so EVERY renderer reads a step's
// request shape and a payload field's request-location the same way — whether the
// model carries the structured v1.1 fields or a pre-v1.1 string `operation`.
// A pre-v1.1 model (no `request`, no `target`) resolves identically to how the k6
// renderer has always string-parsed it, so existing models stay valid.

/** Split "GET /api/products/{id}" -> { method, path }. Mirrors k6 parseOperation. */
export function parseOperation(operation) {
  const m = /^([A-Z]+)\s+(.*)$/.exec(String(operation || '').trim());
  if (!m) return { method: 'GET', pathTemplate: String(operation || '').trim() };
  return { method: m[1], pathTemplate: m[2] };
}

/**
 * Resolve a step's request shape. Prefers the structured G-R1 `step.request`;
 * falls back to string-parsing `step.operation` for pre-v1.1 models.
 * Always returns { method, pathTemplate, queryParams, headers, bodyPayloadRef }.
 */
export function resolveRequest(step) {
  const req = step && step.request;
  if (req && typeof req === 'object') {
    const parsed = parseOperation(step.operation);
    return {
      method: req.method || parsed.method,
      pathTemplate: req.pathTemplate || parsed.pathTemplate,
      queryParams: req.queryParams || {},
      headers: req.headers || {},
      bodyPayloadRef: req.bodyPayloadRef != null ? req.bodyPayloadRef : step.payloadRef || null,
    };
  }
  const parsed = parseOperation(step && step.operation);
  return {
    method: parsed.method,
    pathTemplate: parsed.pathTemplate,
    queryParams: {},
    headers: {},
    bodyPayloadRef: (step && step.payloadRef) || null,
  };
}

const BODY_METHODS = new Set(['POST', 'PUT', 'PATCH']);
export function methodHasBody(method) {
  return BODY_METHODS.has(String(method || '').toUpperCase());
}

/**
 * Resolve a payload field's request-location. Prefers the structured G-P1
 * `field.target`; falls back to the §4 v0.x convention (scalar fields go into the
 * request body under their own name). Returns { into, as }.
 */
export function resolveFieldTarget(field) {
  const t = field && field.target;
  if (t && typeof t === 'object' && t.into) {
    return { into: t.into, as: t.as || field.name };
  }
  return { into: 'body_field', as: field.name };
}

/**
 * Enumerate the edge HTTP steps a renderer can directly drive, vs non-http steps
 * (grpc/db/mq/cache) which are topology/baseline only (G-X1). Returns
 * { driven: Step[], undriven: Step[] } for a journey.
 */
export function partitionDrivableSteps(journey) {
  const driven = [];
  const undriven = [];
  for (const s of (journey && journey.steps) || []) {
    if (s.callType === 'http') driven.push(s);
    else undriven.push(s);
  }
  return { driven, undriven };
}
