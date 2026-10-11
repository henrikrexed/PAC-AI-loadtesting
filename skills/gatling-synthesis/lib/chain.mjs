// chain.mjs — request chaining / correlation (G2, research §4.1).
//
// Gatling saves a value on the response of the SOURCE step via a `.check(...saveAs)`
// and reads it from the session as `#{attr}` in a later request. This differs from
// k6 (which reads a stored response object at the consuming step): here we must
// attach the extractor to the PRODUCER. So we pre-scan a journey and return:
//   - savesByStep[sourceStepId]  = [ "<gatling check>.saveAs(\"<key>\")" , ... ]
//   - injectsByStep[consumerId]  = [ { into, as, key } , ... ]
// The session-attribute key is deterministic: c_<consumerStepId>_<inject.as>.

/** Deterministic session-attribute key for one correlation. */
export function saveKey(consumerStepId, injectAs) {
  const safe = (s) => String(s).replace(/[^A-Za-z0-9_]/g, '_');
  return `c_${safe(consumerStepId)}_${safe(injectAs)}`;
}

/** Normalize an extract path to a Gatling JsonPath ("$"-rooted). */
export function toJsonPath(path) {
  const p = String(path || '').trim();
  if (!p) return '$';
  if (p.startsWith('$')) return p;
  return p.startsWith('[') ? `$${p}` : `$.${p}`;
}

/** Canonicalize an HTTP header name: set-cookie -> Set-Cookie. */
export function canonHeader(name) {
  return String(name)
    .split('-')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w))
    .join('-');
}

function scalaStr(s) {
  return JSON.stringify(String(s));
}

/**
 * Render the Gatling check expression (without a leading dot) that saves an
 * extracted value into session attribute `key`. `approx` collects any
 * approximations this extractor needed (for supports()/warnings).
 */
export function extractCheck(extract, key, approx = []) {
  const from = (extract && extract.from) || 'body_json';
  const path = (extract && extract.path) || '';
  switch (from) {
    case 'body_json':
      return `jsonPath(${scalaStr(toJsonPath(path))}).saveAs(${scalaStr(key)})`;
    case 'header': {
      if (path.includes(':')) {
        const [h, sub] = path.split(':');
        // cookie-style sub-selector: extract `sub=<value>` out of the header via regex.
        return `headerRegex(${scalaStr(canonHeader(h))}, ${scalaStr(`${sub}=([^;]+)`)}).saveAs(${scalaStr(key)})`;
      }
      return `header(${scalaStr(canonHeader(path))}).saveAs(${scalaStr(key)})`;
    }
    case 'regex':
      return `regex(${scalaStr(path)}).saveAs(${scalaStr(key)})`;
    case 'body_html':
      approx.push({
        feature: 'correlates.extract.from=body_html',
        reason: 'Gatling has no native HTML-DOM extractor',
        approximation: 'regex over the raw response body',
      });
      return `regex(${scalaStr(path)}).saveAs(${scalaStr(key)})`;
    default:
      return `jsonPath(${scalaStr(toJsonPath(path))}).saveAs(${scalaStr(key)})`;
  }
}

/**
 * Plan a journey's correlations. Returns { savesByStep, injectsByStep, approx }.
 */
export function planCorrelations(journey) {
  const savesByStep = {};
  const injectsByStep = {};
  const approx = [];
  for (const step of journey.steps || []) {
    for (const c of step.correlates || []) {
      const key = saveKey(step.id, c.inject.as);
      const check = extractCheck(c.extract, key, approx);
      (savesByStep[c.sourceStepId] = savesByStep[c.sourceStepId] || []).push(check);
      (injectsByStep[step.id] = injectsByStep[step.id] || []).push({
        into: c.inject.into,
        as: c.inject.as,
        key,
      });
    }
  }
  return { savesByStep, injectsByStep, approx };
}
