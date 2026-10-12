// chain.js — request-chaining / correlation helpers (G2, methodology §3.3 rule 3).
//
// Pure, dependency-free JS so it is importable BOTH from a generated k6 script
// (k6 accepts plain-JS local imports) AND from Node unit tests. No k6 globals
// are referenced here; the generated script decides what to do on a broken chain.

/**
 * Resolve a dotted / bracketed path against a parsed object.
 *   "products[0].id"  ->  obj.products[0].id
 * Returns null (never throws) when any segment is missing.
 */
export function resolvePath(obj, path) {
  if (obj == null || typeof path !== 'string' || path.length === 0) return null;
  const segments = path
    .replace(/\[(\d+)\]/g, '.$1') // products[0] -> products.0
    .split('.')
    .filter((s) => s.length > 0);
  let cur = obj;
  for (const seg of segments) {
    if (cur == null || typeof cur !== 'object') return null;
    if (!(seg in cur)) return null;
    cur = cur[seg];
  }
  return cur == null ? null : cur;
}

/**
 * Extract a correlation value from a response-like object `{ body, headers }`.
 * `spec` = { from: 'body_json'|'header'|'body_html'|'body_regex', path }.
 * Returns null on any failure — the caller (generated step) MUST treat null as
 * a broken chain and fail fast.
 */
export function extract(res, spec) {
  if (res == null || spec == null) return null;
  const { from, path } = spec;
  try {
    switch (from) {
      case 'body_json': {
        const body = typeof res.body === 'string' ? JSON.parse(res.body) : res.body;
        return resolvePath(body, path);
      }
      case 'header': {
        const headers = res.headers || {};
        // case-insensitive header lookup
        const want = String(path).toLowerCase();
        for (const k of Object.keys(headers)) {
          if (k.toLowerCase() === want) return headers[k] == null ? null : headers[k];
        }
        return null;
      }
      case 'body_html': {
        // path = "left||right"; returns text strictly between the two markers.
        const body = typeof res.body === 'string' ? res.body : String(res.body ?? '');
        const sep = String(path).split('||');
        if (sep.length !== 2) return null;
        const [left, right] = sep;
        const start = body.indexOf(left);
        if (start < 0) return null;
        const from2 = start + left.length;
        const end = body.indexOf(right, from2);
        if (end < 0) return null;
        return body.slice(from2, end);
      }
      case 'body_regex': {
        const body = typeof res.body === 'string' ? res.body : String(res.body ?? '');
        const m = new RegExp(path).exec(body);
        return m && m[1] != null ? m[1] : null;
      }
      default:
        return null;
    }
  } catch (_e) {
    return null;
  }
}

/**
 * Broken-chain signal. In a k6 script this is wired to `fail()` + early return
 * so the iteration aborts immediately (methodology §3.3 rule 3: "fail the chain
 * on broken correlation"). In Node it throws a typed error the tests assert on.
 */
export class BrokenChainError extends Error {
  constructor(stepId, varName) {
    super(`broken chain at step=${stepId}: correlation ${varName} extracted null`);
    this.name = 'BrokenChainError';
    this.stepId = stepId;
    this.varName = varName;
  }
}

export function failChain(stepId, varName) {
  throw new BrokenChainError(stepId, varName);
}

/**
 * Pure null-check used by both the Node tests and (mirrored inline) by the
 * generated k6 steps: returns the extracted value, or raises BrokenChainError
 * when it is null/undefined. The generated k6 script performs the equivalent
 * check with k6's own `fail()` so the iteration is marked failed in k6 metrics.
 */
export function requireValue(value, stepId, varName) {
  if (value == null) failChain(stepId, varName);
  return value;
}
