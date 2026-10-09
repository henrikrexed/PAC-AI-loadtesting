// correlate.mjs — codegen-time rendering of request chaining / correlation (G2, §3.3 rule 3).
//
// Produces JS source fragments baked into the generated k6 step. The runtime
// extract() + null-guard + k6 fail() implement the "fail fast on broken chain"
// rule. Injection targets (header / path_param / query_param / body_field) are
// resolved here at codegen time so the generated step stays explicit.

/** Split "GET /api/products/{id}" into { method, path }. */
export function parseOperation(operation) {
  const m = /^([A-Z]+)\s+(.*)$/.exec(String(operation).trim());
  if (!m) return { method: 'GET', path: String(operation).trim() };
  return { method: m[1], path: m[2] };
}

export function methodHasBody(method) {
  return method === 'POST' || method === 'PUT' || method === 'PATCH';
}

function jsString(s) {
  return JSON.stringify(String(s));
}

/**
 * Render the correlation-extraction block for one consuming step.
 * Returns { lines, injections } where injections maps inject target ->
 * { into, as, expr } with `expr` the JS expression yielding the value.
 */
export function renderCorrelations(step) {
  const lines = [];
  const injections = [];
  const correlates = step.correlates || [];
  correlates.forEach((c, i) => {
    const v = `corr${i}`;
    const spec = jsExtractSpec(c.extract);
    lines.push(`      const ${v} = extract(responses[${jsString(c.sourceStepId)}], ${spec});`);
    lines.push(
      `      if (${v} === null || ${v} === undefined) { chainBroken.add(1, { step: ${jsString(step.id)} }); fail(${jsString(
        `broken chain at step=${step.id}: correlation from ${c.sourceStepId} (${c.inject.into} ${c.inject.as}) extracted null`
      )}); }`
    );
    injections.push({ into: c.inject.into, as: c.inject.as, expr: v });
  });
  return { lines, injections };
}

function jsExtractSpec(extract) {
  return `{ from: ${jsString(extract.from)}, path: ${jsString(extract.path)} }`;
}

/**
 * Render the URL expression (template literal body, without surrounding
 * backticks) applying path_param and query_param injections, plus any
 * cache-key-pool key bound to the single path token.
 *   base     — JS expr for the base URL (e.g. "BASE")
 *   path     — operation path, e.g. "/api/products/{id}"
 *   injections — from renderCorrelations
 *   poolKeyExpr — optional JS expr for a cache-key value to fill the path token
 */
export function renderUrl(base, path, injections, poolKeyExpr) {
  let out = path;
  const pathInjections = injections.filter((j) => j.into === 'path_param');
  for (const j of pathInjections) {
    out = replaceToken(out, j.as, `\${encodeURIComponent(${j.expr})}`);
  }
  // bind a cache-key pool value to the remaining single {token}, if any
  if (poolKeyExpr) {
    const tok = soleToken(out);
    if (tok) out = replaceToken(out, tok, `\${encodeURIComponent(${poolKeyExpr})}`);
  }
  const queryInjections = injections.filter((j) => j.into === 'query_param');
  if (queryInjections.length > 0) {
    const sep = out.includes('?') ? '&' : '?';
    const qs = queryInjections
      .map((j) => `${encodeURIComponent(j.as)}=\${encodeURIComponent(${j.expr})}`)
      .join('&');
    out = `${out}${sep}${qs}`;
  }
  return `\`\${${base}}${out}\``;
}

function replaceToken(path, token, replacement) {
  // supports {token} and :token styles
  return path.replace(new RegExp(`\\{${escapeRe(token)}\\}|:${escapeRe(token)}(?=/|$)`), replacement);
}

function soleToken(path) {
  const m = path.match(/\{([^}]+)\}/g);
  if (m && m.length === 1) return m[0].slice(1, -1);
  return null;
}

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Render the request-body expression. Starts from a payload-record expr (or {})
 * and layers body_field injections on top.
 * Returns a JS expression (object), or null when there is no body.
 */
export function renderBody(payloadRecordExpr, injections) {
  const bodyInjections = injections.filter((j) => j.into === 'body_field');
  if (!payloadRecordExpr && bodyInjections.length === 0) return null;
  const base = payloadRecordExpr || '{}';
  if (bodyInjections.length === 0) return base;
  const fields = bodyInjections.map((j) => `${jsKey(j.as)}: ${j.expr}`).join(', ');
  return `Object.assign({}, ${base}, { ${fields} })`;
}

/**
 * Render header injections as the first argument to syntheticParams().
 * Returns a JS object-literal expression (possibly "{}").
 */
export function renderHeaderInjections(injections) {
  const headerInjections = injections.filter((j) => j.into === 'header');
  if (headerInjections.length === 0) return '{}';
  const fields = headerInjections.map((j) => `${jsKey(j.as)}: ${j.expr}`).join(', ');
  return `{ ${fields} }`;
}

function jsKey(k) {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(k) ? k : JSON.stringify(k);
}
