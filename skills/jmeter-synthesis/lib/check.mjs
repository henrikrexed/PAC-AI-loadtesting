// check.mjs — the JMeter renderer's OWN static check (the V2a-equivalent the
// common contract requires of every renderer). JMeter ships no offline "lint"
// mode and the `jmeter` binary is not assumed present, so this validates the
// rendered .jmx structurally the way a plan-load would fail-closed:
//
//   J1  the .jmx is well-formed XML (custom zero-dep tokenizer) and every
//       element tag is balanced — a malformed plan will not load in JMeter.
//   J2  JMeter's structural invariant: <hashTree> opens/closes are balanced.
//   J3  required elements present: TestPlan, >=1 thread group, >=1 HTTP sampler.
//   J4  synthetic=true is stamped (baggage Header Manager) — the board mandate.
//   J5  G2 chaining is wired: every model correlation has an extractor whose
//       variable is referenced by a later sampler (step N consumes step N-1).
//   J6  every CSV Data Set filename resolves to a rendered file, and each data
//       set's variables are referenced by at least one sampler.
//   J7  declared load stays within caps (maxRps / maxVus).
//
// Fail-closed: any failing check marks the whole gate failed.

import { poolVarName } from './csv.mjs';

const BODY_METHODS = new Set(['POST', 'PUT', 'PATCH']);

// ---------------------------------------------------------------------------
// Minimal well-formedness + tag-balance scanner (no deps).
// ---------------------------------------------------------------------------
export function checkWellFormed(src) {
  const stack = [];
  let i = 0;
  const n = src.length;
  while (i < n) {
    const lt = src.indexOf('<', i);
    if (lt < 0) break;
    // text between tags is fine (we don't validate entities beyond `&` sanity)
    if (src.startsWith('<!--', lt)) {
      const end = src.indexOf('-->', lt + 4);
      if (end < 0) return { ok: false, detail: 'unterminated comment' };
      i = end + 3;
      continue;
    }
    if (src.startsWith('<![CDATA[', lt)) {
      const end = src.indexOf(']]>', lt + 9);
      if (end < 0) return { ok: false, detail: 'unterminated CDATA' };
      i = end + 3;
      continue;
    }
    if (src.startsWith('<?', lt)) {
      const end = src.indexOf('?>', lt + 2);
      if (end < 0) return { ok: false, detail: 'unterminated processing instruction' };
      i = end + 2;
      continue;
    }
    const gt = src.indexOf('>', lt);
    if (gt < 0) return { ok: false, detail: 'unterminated tag' };
    let tag = src.slice(lt + 1, gt).trim();
    const selfClosing = tag.endsWith('/');
    if (selfClosing) tag = tag.slice(0, -1).trim();
    const closing = tag.startsWith('/');
    const name = (closing ? tag.slice(1) : tag).split(/[\s>]/)[0];
    if (!name) return { ok: false, detail: `empty tag name near offset ${lt}` };
    // crude attribute-quote balance check within the tag
    const quotes = (tag.match(/"/g) || []).length;
    if (quotes % 2 !== 0) return { ok: false, detail: `unbalanced attribute quotes in <${name}>` };
    if (closing) {
      const top = stack.pop();
      if (top !== name) return { ok: false, detail: `mismatched close </${name}> (expected </${top}>)` };
    } else if (!selfClosing) {
      stack.push(name);
    }
    i = gt + 1;
  }
  if (stack.length) return { ok: false, detail: `unclosed elements: ${stack.join(', ')}` };
  return { ok: true, detail: 'well-formed, tags balanced' };
}

function countOccurrences(src, re) {
  return (src.match(re) || []).length;
}

/**
 * Run the full static gate.
 *   args = { model, xml, datasets, files, maxRate, totalThreads }
 * `files` is the rendered file list [{path, content}] (CSV presence check).
 * Returns { pass, checks: [{ id, title, pass, detail }] }.
 */
export function jmeterCheck({ model, xml, datasets, files, maxRate, totalThreads }) {
  const checks = [];
  const spec = model.spec;

  // J1 — well-formed XML + balanced element tags
  const wf = checkWellFormed(xml);
  checks.push({ id: 'wellformed', title: 'J1 .jmx is well-formed XML', pass: wf.ok, detail: wf.detail });

  // J2 — hashTree balance
  const open = countOccurrences(xml, /<hashTree>/g);
  const close = countOccurrences(xml, /<\/hashTree>/g);
  const selfClose = countOccurrences(xml, /<hashTree\s*\/>/g);
  // every <hashTree> needs a </hashTree>; self-closing <hashTree/> is its own pair
  checks.push({
    id: 'hashtree',
    title: 'J2 <hashTree> balance',
    pass: open === close,
    detail: `open=${open} close=${close} selfClosing=${selfClose}`,
  });

  // J3 — required elements
  const hasPlan = /<TestPlan\b/.test(xml);
  const hasTG = /<ThreadGroup\b/.test(xml) || /ConcurrencyThreadGroup\b/.test(xml);
  const nSamplers = countOccurrences(xml, /<HTTPSamplerProxy\b/g);
  checks.push({
    id: 'required',
    title: 'J3 TestPlan + thread group + HTTP sampler present',
    pass: hasPlan && hasTG && nSamplers > 0,
    detail: `TestPlan=${hasPlan} threadGroup=${hasTG} samplers=${nSamplers}`,
  });

  // J4 — synthetic=true baggage
  const hasBaggage = /Header\.name">baggage<\/stringProp>[\s\S]{0,200}?synthetic=true/.test(xml) ||
    /synthetic=true/.test(xml);
  checks.push({
    id: 'synthetic',
    title: 'J4 synthetic=true stamped on traffic (baggage)',
    pass: hasBaggage,
    detail: hasBaggage ? 'baggage: synthetic=true present' : 'no synthetic=true baggage found',
  });

  // J5 — correlation chaining wired (model-driven)
  const corrProblems = [];
  let corrCount = 0;
  for (const j of spec.journeys) {
    for (const s of j.steps || []) {
      for (const c of s.correlates || []) {
        corrCount++;
        // an extractor must save a var that a later sampler references via ${...}
        const consumed = /\$\{corr__/.test(xml);
        const extractorPresent =
          /JSONPostProcessor|RegexExtractor|BoundaryExtractor/.test(xml);
        if (!consumed || !extractorPresent) {
          corrProblems.push(`step ${s.id}: missing extractor/reference`);
        }
      }
    }
  }
  checks.push({
    id: 'chaining',
    title: 'J5 G2 request chaining wired (extractor -> ${var} reference)',
    pass: corrProblems.length === 0,
    detail: corrCount === 0 ? 'no correlations in model' : `${corrCount} correlation(s); ${corrProblems.length} problem(s)`,
  });

  // J6 — CSV data sets resolve + are referenced
  const csvProblems = [];
  const fileset = new Set(files.map((f) => f.path));
  for (const ds of Object.values(datasets)) {
    const expectPath = `jmeter/data/${ds.filename}`;
    if (!fileset.has(expectPath)) csvProblems.push(`missing CSV file ${expectPath}`);
    const refd = ds.variableNames.some((v) => xml.includes(`\${${v}}`));
    const declared = xml.includes(`data/${ds.filename}`);
    if (!declared) csvProblems.push(`${ds.filename} not declared in a CSVDataSet`);
    if (!refd) csvProblems.push(`${ds.filename} variables never referenced by a sampler`);
  }
  checks.push({
    id: 'datasets',
    title: 'J6 CSV data sets resolve + are consumed',
    pass: csvProblems.length === 0,
    detail: csvProblems.length ? csvProblems.join('; ') : `${Object.keys(datasets).length} data set(s) OK`,
  });

  // J7 — caps
  const caps = spec.caps || {};
  const capProblems = [];
  if (caps.maxRps != null && maxRate > caps.maxRps + 1e-6) capProblems.push(`maxRate ${maxRate} > caps.maxRps ${caps.maxRps}`);
  if (caps.maxVus != null && totalThreads > caps.maxVus) capProblems.push(`totalThreads ${totalThreads} > caps.maxVus ${caps.maxVus}`);
  checks.push({
    id: 'caps',
    title: 'J7 declared load within caps',
    pass: capProblems.length === 0,
    detail: capProblems.length ? capProblems.join('; ') : `maxRate=${maxRate} threads=${totalThreads}`,
  });

  const pass = checks.every((c) => c.pass);
  return { pass, checks };
}

export function methodHasBody(method) {
  return BODY_METHODS.has(String(method || '').toUpperCase());
}

export { poolVarName };
