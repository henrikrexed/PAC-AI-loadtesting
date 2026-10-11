// simulation.mjs — model -> Gatling Scala simulation + JSON feeders (research §4.1).
//
// Emits ONE Simulation class: one httpProtocol carrying the synthetic=true baggage
// header + W3C trace-context propagation, one ChainBuilder per journey, a single
// scenario that mixes journeys with `.randomSwitch` weights, and a setUp() whose
// injection profile comes from the arrival profile (injection.mjs). Deterministic,
// network-free, no disk writes — the pure core behind the Renderer adapter.

import { buildInjection } from './injection.mjs';
import { buildFeeder } from './feeders.mjs';
import { planCorrelations, saveKey } from './chain.mjs';
import { collectUnsupported } from './capabilities.mjs';
import { resolveRequest, methodHasBody } from '../../renderer-kit/lib/model-access.mjs';

const GATLING_METHOD = { GET: 'get', POST: 'post', PUT: 'put', PATCH: 'patch', DELETE: 'delete', HEAD: 'head', OPTIONS: 'options' };

function scalaStr(s) {
  return JSON.stringify(String(s));
}

/** PascalCase identifier for the Simulation class. */
function simClassName(name) {
  const base = String(name).split(/[^A-Za-z0-9]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join('');
  const safe = /^[A-Za-z]/.test(base) ? base : `Sim${base}`;
  return `${safe}Simulation`;
}

/** Safe lowerCamel val identifier for a journey / feeder. */
function valName(id, suffix = '') {
  const parts = String(id).split(/[^A-Za-z0-9]+/).filter(Boolean);
  let s = parts.map((w, i) => (i === 0 ? w[0].toLowerCase() + w.slice(1) : w[0].toUpperCase() + w.slice(1))).join('');
  if (!/^[A-Za-z]/.test(s)) s = `j${s}`;
  return `${s}${suffix}`;
}

/** Format a journey weight (0..1) as a Gatling randomSwitch percentage Double literal. */
function pct(weight) {
  const v = Math.round((Number(weight) || 0) * 100 * 1e4) / 1e4;
  return Number.isInteger(v) ? `${v}.0` : String(v);
}

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Replace a {t} / [t] / :t path token with a replacement string. */
function replaceToken(path, token, repl) {
  const e = escapeRe(token);
  return path.replace(new RegExp(`\\{${e}\\}|\\[${e}\\]|:${e}(?=/|$)`, 'g'), repl);
}

/** Find all {t} / [t] / :t tokens in a path template. */
function findTokens(path) {
  const t = new Set();
  let m;
  const re = /\{([^}]+)\}|\[([^\]]+)\]/g;
  while ((m = re.exec(path))) t.add(m[1] || m[2]);
  const re2 = /:([A-Za-z_][A-Za-z0-9_]*)/g;
  while ((m = re2.exec(path))) t.add(m[1]);
  return [...t];
}

/** Gatling think-time pause fragment (NO leading dot) for a step's thinkTime, or null. */
function pauseFragment(thinkTime) {
  if (!thinkTime) return null;
  const d = thinkTime.distribution;
  if (d === 'uniform' && thinkTime.minMs != null && thinkTime.maxMs != null) {
    return `pause(${thinkTime.minMs}.milliseconds, ${thinkTime.maxMs}.milliseconds)`;
  }
  // constant / exponential / empirical -> a single-value mean pause.
  // (exponential/empirical are declared approximations — see capabilities.mjs.)
  const meanMs = thinkTime.meanMs != null ? thinkTime.meanMs
    : (thinkTime.samples && thinkTime.samples.length ? Math.round(thinkTime.samples.reduce((a, b) => a + b, 0) / thinkTime.samples.length) : 0);
  return `pause(${meanMs}.milliseconds)`;
}

/** Render one journey as a ChainBuilder val. Returns { name, lines, poolsUsed }. */
function renderJourney(journey, spec, injectsByStep, savesByStep) {
  const name = valName(journey.id);
  const poolsUsed = [];
  for (const s of journey.steps || []) {
    if (s.payloadRef && !poolsUsed.includes(s.payloadRef) && (spec.payloads || {})[s.payloadRef]) poolsUsed.push(s.payloadRef);
  }
  const fedFields = new Set();
  for (const ref of poolsUsed) {
    for (const f of ((spec.payloads || {})[ref].fields) || []) fedFields.add(f.name);
  }

  const steps = (journey.steps || []).filter((s) => (s.callType || 'http') === 'http');

  // Each chain part is emitted WITHOUT a leading dot; assembly below joins them so
  // the first part starts the expression and every later part continues it with a
  // leading `.` (the only newline-safe way to chain the Gatling DSL in Scala).
  const parts = [];
  // lead with feeders so every HTTP step in this journey can read #{field}
  for (const ref of poolsUsed) parts.push(`feed(${valName(ref, 'Feeder')})`);

  steps.forEach((step) => {
    const req = resolveRequest(step);
    const injects = injectsByStep[step.id] || [];
    const saves = savesByStep[step.id] || [];

    // --- URL (path tokens: correlation path_param first, then fed fields) ---
    let path = req.pathTemplate;
    for (const inj of injects.filter((i) => i.into === 'path_param')) path = replaceToken(path, inj.as, `#{${inj.key}}`);
    for (const tok of findTokens(path)) if (fedFields.has(tok)) path = replaceToken(path, tok, `#{${tok}}`);
    const queryInj = injects.filter((i) => i.into === 'query_param');
    if (queryInj.length) {
      const sep = path.includes('?') ? '&' : '?';
      path += sep + queryInj.map((i) => `${i.as}=#{${i.key}}`).join('&');
    }

    const method = GATLING_METHOD[req.method] || 'get';
    const reqLines = [`      http(${scalaStr(step.id)}).${method}(${scalaStr(path)})`];

    // --- header injections ---
    for (const inj of injects.filter((i) => i.into === 'header')) {
      reqLines.push(`        .header(${scalaStr(inj.as)}, ${scalaStr(`#{${inj.key}}`)})`);
    }

    // --- body (record-pool fields + body_field injections) ---
    if (methodHasBody(req.method)) {
      const bodyFields = {};
      const pool = (spec.payloads || {})[step.payloadRef];
      if (pool && !pool.cacheProfile) for (const f of pool.fields || []) bodyFields[f.name] = `#{${f.name}}`;
      for (const inj of injects.filter((i) => i.into === 'body_field')) bodyFields[inj.as] = `#{${inj.key}}`;
      const entries = Object.entries(bodyFields);
      const json = entries.length ? '{ ' + entries.map(([k, v]) => `${scalaStr(k)}: ${scalaStr(v)}`).join(', ') + ' }' : '{}';
      reqLines.push(`        .body(StringBody(${scalaStr(json)})).asJson`);
    }

    // --- checks: status, then any saveAs this step owns as a correlation SOURCE ---
    reqLines.push(`        .check(status.lt(500))`);
    for (const chk of saves) reqLines.push(`        .check(${chk})`);

    parts.push(`exec(\n${reqLines.join('\n')}\n    )`);
    const pause = pauseFragment(step.thinkTime);
    if (pause) parts.push(pause);
  });

  if (parts.length === 0) parts.push('exec(session => session) // no drivable HTTP steps');
  // first part starts the expression; the rest continue with a leading dot
  const body = parts.map((p, i) => (i === 0 ? `    ${p}` : `    .${p}`)).join('\n');
  const lines = `  val ${name}: ChainBuilder =\n${body}`;
  return { name, lines, poolsUsed };
}

/**
 * Build the full Gatling artifact set in memory.
 * Returns { files:[{path,content}], warnings, injection, feeders }.
 */
export function buildSimulation(model, _opts = {}) {
  const spec = model.spec;
  const warnings = [];
  const files = [];

  // capability report -> warnings (mirrors renderer.supports())
  for (const u of collectUnsupported(model)) {
    warnings.push(`gatling: ${u.feature} — ${u.reason}${u.approximation ? ` (approx: ${u.approximation})` : ''}`);
  }

  // feeders for every referenced pool
  const referenced = new Set();
  for (const j of spec.journeys || []) for (const s of j.steps || []) if (s.payloadRef) referenced.add(s.payloadRef);
  const feeders = {};
  for (const ref of referenced) {
    if (!(spec.payloads || {})[ref]) continue;
    const feeder = buildFeeder(model, ref);
    feeders[ref] = feeder;
    files.push({ path: `gatling/feeders/${ref}.json`, content: JSON.stringify(feeder.records, null, 2) + '\n' });
  }

  // injection profile
  const injection = buildInjection(spec.arrivalProfile);
  warnings.push(...injection.warnings);

  // per-journey chains + correlation plans
  const journeyVals = [];
  const feederDecls = [];
  const declaredFeeders = new Set();
  for (const j of spec.journeys || []) {
    const { savesByStep, injectsByStep } = planCorrelations(j);
    const jr = renderJourney(j, spec, injectsByStep, savesByStep);
    journeyVals.push(jr);
    for (const ref of jr.poolsUsed) {
      if (declaredFeeders.has(ref)) continue;
      declaredFeeders.add(ref);
      feederDecls.push(`  val ${valName(ref, 'Feeder')} = jsonFile("feeders/${ref}.json").random`);
    }
  }

  const className = simClassName(model.metadata.name);
  const header = [
    '// AUTO-GENERATED by gatling-synthesis (ISI-5658). Do not edit by hand.',
    `// Source model: ${model.metadata.name} rev ${(model.status && model.status.revision) ?? '?'}`,
  ];
  const unsupported = collectUnsupported(model);
  if (unsupported.length) {
    header.push('//');
    header.push('// CAPABILITY REPORT (approximations applied — confirm at VALIDATE):');
    for (const u of unsupported) header.push(`//   - ${u.feature}: ${u.reason}${u.approximation ? ` -> ${u.approximation}` : ''}`);
  }

  const imports = [
    'package isi.loadtest',
    '',
    'import scala.concurrent.duration._',
    'import io.gatling.core.Predef._',
    'import io.gatling.http.Predef._',
  ];

  const protocol = [
    `class ${className} extends Simulation {`,
    '',
    `  val baseUrl: String = sys.env.getOrElse("BASE_URL", "http://localhost:8080")`,
    '',
    '  // synthetic=true identity: W3C `baggage` header on EVERY request (methodology P4,',
    '  // §7.7) — the collector/SDK baggage span processor promotes it to the queryable',
    '  // span attribute `synthetic`. W3C trace-context propagation joins backend spans.',
    '  val httpProtocol = http',
    '    .baseUrl(baseUrl)',
    '    .header("baggage", "synthetic=true")',
    '    .acceptHeader("application/json")',
    '',
  ];

  // scenario: single scenario, journey mix via randomSwitch (research §4.1)
  const scenarioName = valName(model.metadata.name, 'Scenario');
  const scenarioLines = [];
  if (journeyVals.length === 1) {
    scenarioLines.push(`  val ${scenarioName} = scenario(${scalaStr(model.metadata.name)}).exec(${journeyVals[0].name})`);
  } else {
    scenarioLines.push(`  val ${scenarioName} = scenario(${scalaStr(model.metadata.name)}).randomSwitch(`);
    scenarioLines.push(
      spec.journeys.map((j, i) => `    ${pct(j.weight)} -> ${journeyVals[i].name}`).join(',\n')
    );
    scenarioLines.push('  )');
  }

  const injLines = injection.steps.map((s) => `      ${s}`).join(',\n');
  const setup = [
    '',
    `  // Little's Law ceiling: ~${injection.maxConcurrent} concurrent users at peak (model ${injection.model} arrival).`,
    '  setUp(',
    `    ${scenarioName}.inject(`,
    injLines,
    '    )',
    '  ).protocols(httpProtocol)',
    '}',
  ];

  const content = [
    ...header,
    '',
    ...imports,
    '',
    ...protocol,
    ...(feederDecls.length ? ['  // feeders (G4 cache-avoidance: pre-generated Zipf pools)', ...feederDecls, ''] : []),
    ...journeyVals.map((jv) => jv.lines + '\n'),
    ...scenarioLines,
    ...setup,
    '',
  ].join('\n');

  files.push({ path: `gatling/${className}.scala`, content });

  return { files, warnings, injection, feeders };
}
