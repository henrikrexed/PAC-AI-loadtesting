// jmx.mjs — approved workload-model.json -> a JMeter .jmx test plan (§4.1 mapping).
//
// Deterministic, no network, no wall-clock. One Thread-Group-equivalent per
// journey; one HTTP sampler per drivable HTTP step; correlation extractors wired
// source->consumer (G2); native timers for think-time (G-E1 empirical -> JSR223
// approx); CSV Data Set Config per payload pool (G4); and a Header Manager that
// stamps `baggage: synthetic=true` on every request (the board-mandated synthetic
// flag, same as k6).
//
// Executor mapping (§4.1):
//   open model   -> jp@gc Concurrency Thread Group + Throughput Shaping Timer
//   closed model -> native Thread Group (constant/ramping users)
// Little's-Law expectedConcurrency x journey weight -> thread ceiling (clamped to caps).

import {
  resolveRequest,
  resolveFieldTarget,
  methodHasBody,
  partitionDrivableSteps,
} from '../../renderer-kit/lib/model-access.mjs';
import { durationToSeconds, enforceRampDown } from '../../k6-synthesis/lib/arrival.mjs';
import { poolVarName } from './csv.mjs';

export const CHAIN_BROKEN_SENTINEL = '__CHAIN_BROKEN__';
const BAGGAGE_HEADER = 'baggage';
const BAGGAGE_VALUE = 'synthetic=true';

// ---------------------------------------------------------------------------
// XML + JMeter property primitives
// ---------------------------------------------------------------------------
function xml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function sanitize(s) {
  return String(s).replace(/[^A-Za-z0-9_]/g, '_');
}
function sp(name, value) {
  return `<stringProp name="${xml(name)}">${xml(value)}</stringProp>`;
}
function bp(name, value) {
  return `<boolProp name="${xml(name)}">${value ? 'true' : 'false'}</boolProp>`;
}

// ---------------------------------------------------------------------------
// Correlation pre-pass (G2): extractors live on the SOURCE sampler; injections
// are baked into the CONSUMER sampler. Dedupe identical extractions on one source.
// ---------------------------------------------------------------------------
function pathSlug(p) {
  const s = sanitize(String(p).replace(/^\$\.?/, ''));
  return s.replace(/^_+|_+$/g, '') || 'val';
}

function buildCorrelations(journey) {
  const extractorsByStep = new Map(); // stepId -> [{varName, from, path, testname}]
  const injectionsByStep = new Map(); // stepId -> [{into, as, varRef}]
  const seen = new Map(); // `${src}|${from}|${path}` -> varName
  const usedVars = new Set();

  for (const step of journey.steps || []) {
    for (const c of step.correlates || []) {
      const key = `${c.sourceStepId}|${c.extract.from}|${c.extract.path}`;
      let varName = seen.get(key);
      if (!varName) {
        let base = `corr__${sanitize(c.sourceStepId)}__${pathSlug(c.extract.path)}`;
        varName = base;
        let n = 1;
        while (usedVars.has(varName)) varName = `${base}_${n++}`;
        usedVars.add(varName);
        seen.set(key, varName);
        const list = extractorsByStep.get(c.sourceStepId) || [];
        list.push({ varName, from: c.extract.from, path: c.extract.path, testname: `extract ${c.inject.as}` });
        extractorsByStep.set(c.sourceStepId, list);
      }
      const inj = injectionsByStep.get(step.id) || [];
      inj.push({ into: c.inject.into, as: c.inject.as, varRef: `\${${varName}}` });
      injectionsByStep.set(step.id, inj);
    }
  }
  return { extractorsByStep, injectionsByStep };
}

// ---------------------------------------------------------------------------
// Extractors
// ---------------------------------------------------------------------------
function normalizeJsonPath(p) {
  const s = String(p).trim();
  if (s.startsWith('$')) return s;
  return `$.${s}`;
}

function renderExtractor(ex) {
  if (ex.from === 'body_json') {
    return [
      `<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="${xml(ex.testname)}" enabled="true">`,
      sp('JSONPostProcessor.referenceNames', ex.varName),
      sp('JSONPostProcessor.jsonPathExprs', normalizeJsonPath(ex.path)),
      sp('JSONPostProcessor.match_numbers', '1'),
      sp('JSONPostProcessor.defaultValues', CHAIN_BROKEN_SENTINEL),
      `</JSONPostProcessor>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (ex.from === 'header') {
    // "set-cookie:session" -> capture the named cookie value; else match the header line.
    const colon = ex.path.indexOf(':');
    const regex = colon >= 0 ? `${ex.path.slice(colon + 1)}=([^;\\s]+)` : `${ex.path}:\\s*(.+)`;
    return [
      `<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="${xml(ex.testname)}" enabled="true">`,
      sp('RegexExtractor.useHeaders', 'true'),
      sp('RegexExtractor.refname', ex.varName),
      sp('RegexExtractor.regex', regex),
      sp('RegexExtractor.template', '$1$'),
      sp('RegexExtractor.default', CHAIN_BROKEN_SENTINEL),
      sp('RegexExtractor.match_number', '1'),
      `</RegexExtractor>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (ex.from === 'body_html') {
    // G-E1 approximation: no native HTML selector -> Boundary Extractor best-effort.
    const token = String(ex.path).split(/[.>\s]+/).filter(Boolean).pop() || 'id';
    return [
      `<BoundaryExtractor guiclass="BoundaryExtractorGui" testclass="BoundaryExtractor" testname="${xml(ex.testname)} (body_html~boundary)" enabled="true">`,
      sp('BoundaryExtractor.refname', ex.varName),
      sp('BoundaryExtractor.lboundary', `${token}="`),
      sp('BoundaryExtractor.rboundary', '"'),
      sp('BoundaryExtractor.default', CHAIN_BROKEN_SENTINEL),
      sp('BoundaryExtractor.match_number', '1'),
      sp('BoundaryExtractor.useHeaders', 'false'),
      `</BoundaryExtractor>`,
      `<hashTree/>`,
    ].join('\n');
  }
  // body_regex (and any other) -> Regular Expression Extractor over the body.
  return [
    `<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="${xml(ex.testname)}" enabled="true">`,
    sp('RegexExtractor.useHeaders', 'false'),
    sp('RegexExtractor.refname', ex.varName),
    sp('RegexExtractor.regex', ex.path),
    sp('RegexExtractor.template', '$1$'),
    sp('RegexExtractor.default', CHAIN_BROKEN_SENTINEL),
    sp('RegexExtractor.match_number', '1'),
    `</RegexExtractor>`,
    `<hashTree/>`,
  ].join('\n');
}

// ---------------------------------------------------------------------------
// Timers (think-time)
// ---------------------------------------------------------------------------
function renderTimer(think, warnings, stepId) {
  const d = think.distribution;
  if (d === 'constant') {
    return [
      `<ConstantTimer guiclass="ConstantTimerGui" testclass="ConstantTimer" testname="think ${xml(stepId)}" enabled="true">`,
      sp('ConstantTimer.delay', String(Math.round(think.meanMs ?? 0))),
      `</ConstantTimer>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (d === 'uniform') {
    const min = Math.round(think.minMs ?? 0);
    const range = Math.max(0, Math.round((think.maxMs ?? min) - min));
    return [
      `<UniformRandomTimer guiclass="UniformRandomTimerGui" testclass="UniformRandomTimer" testname="think ${xml(stepId)}" enabled="true">`,
      sp('ConstantTimer.delay', String(min)),
      sp('RandomTimer.range', String(range)),
      `</UniformRandomTimer>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (d === 'gaussian' || d === 'normal') {
    const offset = Math.round(think.meanMs ?? 0);
    const dev = Math.round(think.stddevMs ?? Math.max(1, offset * 0.3));
    return [
      `<GaussianRandomTimer guiclass="GaussianRandomTimerGui" testclass="GaussianRandomTimer" testname="think ${xml(stepId)}" enabled="true">`,
      sp('ConstantTimer.delay', String(offset)),
      sp('RandomTimer.range', String(dev)),
      `</GaussianRandomTimer>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (d === 'exponential' || d === 'poisson') {
    // JMeter's documented continuous-delay timer (§4.1 table).
    return [
      `<PoissonRandomTimer guiclass="PoissonRandomTimerGui" testclass="PoissonRandomTimer" testname="think ${xml(stepId)}" enabled="true">`,
      sp('ConstantTimer.delay', '0'),
      sp('RandomTimer.range', String(Math.round(think.meanMs ?? 0))),
      `</PoissonRandomTimer>`,
      `<hashTree/>`,
    ].join('\n');
  }
  if (d === 'empirical') {
    // G-E1 approximation: JSR223 timer samples the pre-generated empirical list.
    warnings.push(`jmeter: step "${stepId}" uses empirical think-time — approximated by a JSR223 timer`);
    const samples = JSON.stringify((think.samplesMs && think.samplesMs.length ? think.samplesMs : [think.meanMs ?? 1000]));
    const script = [
      `// G-E1 approximation: deterministic walk over the pre-generated empirical samples.`,
      `def samples = ${samples}`,
      `def key = 'EMP_${sanitize(stepId)}'`,
      `def i = (vars.get(key) ?: '0') as int`,
      `vars.put(key, ((i + 1) % samples.size()).toString())`,
      `return samples[i] as long`,
    ].join('\n');
    return [
      `<JSR223Timer guiclass="TestBeanGUI" testclass="JSR223Timer" testname="think ${xml(stepId)} (empirical~jsr223)" enabled="true">`,
      sp('scriptLanguage', 'groovy'),
      sp('script', script),
      `</JSR223Timer>`,
      `<hashTree/>`,
    ].join('\n');
  }
  warnings.push(`jmeter: step "${stepId}" has unknown think-time distribution "${d}" — omitted`);
  return '';
}

// ---------------------------------------------------------------------------
// Path tokens + URL assembly
// ---------------------------------------------------------------------------
function replacePathToken(path, token, value) {
  const t = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`\\{${t}\\}|\\[${t}\\]|:${t}(?=/|$)`);
  return path.replace(re, value);
}
function soleToken(path) {
  const m = path.match(/\{([^}]+)\}|\[([^\]]+)\]/g);
  if (m && m.length === 1) return m[0].slice(1, -1);
  return null;
}

// ---------------------------------------------------------------------------
// One HTTP sampler (+ its child extractors / timer / header manager)
// ---------------------------------------------------------------------------
function renderSampler(step, ctx) {
  const { datasets, injectionsByStep, extractorsByStep, warnings } = ctx;
  const req = resolveRequest(step);
  let path = req.pathTemplate;
  const query = []; // {name, value}
  const bodyFields = []; // {name, value}
  const headers = []; // {name, value}

  const injections = injectionsByStep.get(step.id) || [];
  for (const inj of injections) {
    if (inj.into === 'path_param') path = replacePathToken(path, inj.as, encodeVarInPath(inj.varRef));
    else if (inj.into === 'query_param') query.push({ name: inj.as, value: inj.varRef });
    else if (inj.into === 'header') headers.push({ name: inj.as, value: inj.varRef });
    else bodyFields.push({ name: inj.as, value: inj.varRef }); // body_field (default)
  }

  // payload-pool binding (G-P1 field targets / cache-key)
  if (req.bodyPayloadRef && datasets[req.bodyPayloadRef]) {
    const ds = datasets[req.bodyPayloadRef];
    if (ds.kind === 'cache-key') {
      const varRef = `\${${poolVarName(ds.id, ds.keyField)}}`;
      const tok = soleToken(path);
      if (tok) path = replacePathToken(path, tok, encodeVarInPath(varRef));
      else if (methodHasBody(req.method)) bodyFields.push({ name: ds.keyField, value: varRef });
      else query.push({ name: ds.keyField, value: varRef });
    } else {
      const pool = ctx.model.spec.payloads[ds.id];
      for (const f of pool.fields || []) {
        const target = resolveFieldTarget(f);
        const varRef = `\${${poolVarName(ds.id, f.name)}}`;
        if (target.into === 'path_param') path = replacePathToken(path, target.as, encodeVarInPath(varRef));
        else if (target.into === 'query_param') query.push({ name: target.as, value: varRef });
        else if (target.into === 'header') headers.push({ name: target.as, value: varRef });
        else bodyFields.push({ name: target.as, value: varRef });
      }
    }
  }

  // Dedupe by name keeping the FIRST binding: correlation injections are pushed
  // before payload-pool fields, so a chained value (e.g. the just-viewed productId)
  // wins over the pool's cache-key when both target the same field — no duplicate
  // JSON keys / repeated query params.
  const query2 = dedupeByName(query);
  const bodyFields2 = dedupeByName(bodyFields);
  const headers2 = dedupeByName(headers);

  // assemble query string
  if (query2.length) {
    const sep = path.includes('?') ? '&' : '?';
    path = path + sep + query2.map((q) => `${q.name}=${q.value}`).join('&');
  }

  const hasBody = methodHasBody(req.method);
  const bodyStr = hasBody ? renderJsonBody(bodyFields2) : null;
  if (hasBody) headers2.push({ name: 'Content-Type', value: 'application/json' });

  const lines = [];
  lines.push(
    `<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="${xml(step.id)}" enabled="true">`
  );
  lines.push(`  <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">`);
  lines.push(`    <collectionProp name="Arguments.arguments">`);
  if (hasBody) {
    lines.push(`      <elementProp name="" elementType="HTTPArgument">`);
    lines.push(`        ${bp('HTTPArgument.always_encode', false)}`);
    lines.push(`        ${sp('Argument.value', bodyStr)}`);
    lines.push(`        ${sp('Argument.metadata', '=')}`);
    lines.push(`      </elementProp>`);
  }
  lines.push(`    </collectionProp>`);
  lines.push(`  </elementProp>`);
  lines.push(`  ${sp('HTTPSampler.domain', '')}`);
  lines.push(`  ${sp('HTTPSampler.port', '')}`);
  lines.push(`  ${sp('HTTPSampler.protocol', '')}`);
  lines.push(`  ${sp('HTTPSampler.path', path)}`);
  lines.push(`  ${sp('HTTPSampler.method', req.method)}`);
  lines.push(`  ${bp('HTTPSampler.follow_redirects', true)}`);
  lines.push(`  ${bp('HTTPSampler.use_keepalive', true)}`);
  if (hasBody) lines.push(`  ${bp('HTTPSampler.postBodyRaw', true)}`);
  lines.push(`</HTTPSamplerProxy>`);

  // child hashTree: header manager (injected/content-type), extractors, timer
  const children = [];
  if (headers2.length) children.push(renderHeaderManager(headers2, `headers ${step.id}`));
  for (const ex of extractorsByStep.get(step.id) || []) children.push(renderExtractor(ex));
  if (step.thinkTime) {
    const t = renderTimer(step.thinkTime, warnings, step.id);
    if (t) children.push(t);
  }
  lines.push(`<hashTree>`);
  for (const c of children) lines.push(indent(c, 1));
  lines.push(`</hashTree>`);
  return lines.join('\n');
}

// Variables in a path segment must be URL-safe; JMeter substitutes before send.
function encodeVarInPath(varRef) {
  return varRef;
}

/** Keep the first binding per name (stable order) — avoids duplicate JSON keys /
 * repeated query params / repeated headers when a correlation and a payload field
 * target the same name. */
function dedupeByName(items) {
  const seen = new Set();
  const out = [];
  for (const it of items) {
    if (seen.has(it.name)) continue;
    seen.add(it.name);
    out.push(it);
  }
  return out;
}

function renderJsonBody(bodyFields) {
  if (!bodyFields.length) return '{}';
  const parts = bodyFields.map((f) => `${JSON.stringify(f.name)}: ${JSON.stringify(f.value)}`);
  return `{${parts.join(', ')}}`;
}

function renderHeaderManager(headers, testname) {
  const lines = [];
  lines.push(`<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="${xml(testname)}" enabled="true">`);
  lines.push(`  <collectionProp name="HeaderManager.headers">`);
  for (const h of headers) {
    lines.push(`    <elementProp name="" elementType="Header">`);
    lines.push(`      ${sp('Header.name', h.name)}`);
    lines.push(`      ${sp('Header.value', h.value)}`);
    lines.push(`    </elementProp>`);
  }
  lines.push(`  </collectionProp>`);
  lines.push(`</HeaderManager>`);
  lines.push(`<hashTree/>`);
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Arrival -> Thread Group
// ---------------------------------------------------------------------------
function classifyStages(stages) {
  let rampUp = 0;
  let hold = 0;
  let rampDown = 0;
  for (const s of stages) {
    const sec = durationToSeconds(s.duration);
    if (s.shape === 'ramp_up') rampUp += sec;
    else if (s.shape === 'ramp_down') rampDown += sec;
    else hold += sec; // plateau / steady
  }
  return { rampUp, hold, rampDown, total: rampUp + hold + rampDown };
}

function threadCeiling(expectedConcurrency, weight, caps) {
  const concurrency = expectedConcurrency != null ? expectedConcurrency * weight : 1;
  let threads = Math.max(1, Math.ceil(concurrency * 1.25));
  if (caps && caps.maxVus != null && threads > caps.maxVus) threads = caps.maxVus;
  return threads;
}

function round4(n) {
  return Math.round(n * 1e4) / 1e4;
}

/** Throughput Shaping Timer rows: [startRps, endRps, durationSec] per stage. */
function loadProfileRows(stages, weight) {
  const rows = [];
  let prevEnd = 0;
  for (const s of stages) {
    const target = round4(Number(s.rate) * weight);
    const dur = Math.max(1, Math.round(durationToSeconds(s.duration)));
    let start = prevEnd;
    let end = target;
    if (s.shape === 'plateau' || s.shape === 'steady' || s.shape == null) {
      start = target;
      end = target;
    }
    rows.push([round4(start), round4(end), dur]);
    prevEnd = end;
  }
  return rows;
}

function renderThroughputShapingTimer(rows) {
  const lines = [];
  lines.push(`<kg.apc.jmeter.timers.VariableThroughputTimer guiclass="kg.apc.jmeter.timers.VariableThroughputTimerGui" testclass="kg.apc.jmeter.timers.VariableThroughputTimer" testname="Throughput Shaping Timer" enabled="true">`);
  lines.push(`  <collectionProp name="load_profile">`);
  for (const [start, end, dur] of rows) {
    lines.push(`    <collectionProp name="">`);
    lines.push(`      ${sp('', String(start))}`);
    lines.push(`      ${sp('', String(end))}`);
    lines.push(`      ${sp('', String(dur))}`);
    lines.push(`    </collectionProp>`);
  }
  lines.push(`  </collectionProp>`);
  lines.push(`</kg.apc.jmeter.timers.VariableThroughputTimer>`);
  lines.push(`<hashTree/>`);
  return lines.join('\n');
}

function renderThreadGroupOpen(journey, stages, threads, timing, samplerBlocks, weight) {
  const rows = loadProfileRows(stages, weight);
  const lines = [];
  lines.push(`<com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup guiclass="com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroupGui" testclass="com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup" testname="${xml(journey.id)} (open, w=${journey.weight})" enabled="true">`);
  lines.push(`  <elementProp name="ThreadGroup.main_controller" elementType="com.blazemeter.jmeter.control.VirtualUserController"/>`);
  lines.push(`  ${sp('ThreadGroup.on_sample_error', 'continue')}`);
  lines.push(`  ${sp('TargetLevel', String(threads))}`);
  lines.push(`  ${sp('RampUp', String(Math.max(1, Math.round(timing.rampUp || 1))))}`);
  lines.push(`  ${sp('Steps', '10')}`);
  lines.push(`  ${sp('Hold', String(Math.max(0, Math.round(timing.hold))))}`);
  lines.push(`  ${sp('Unit', 'S')}`);
  lines.push(`  ${sp('Iterations', '')}`);
  lines.push(`  ${bp('ThreadGroup.scheduler', false)}`);
  lines.push(`</com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup>`);
  lines.push(`<hashTree>`);
  lines.push(indent(renderThroughputShapingTimer(rows), 1));
  for (const b of samplerBlocks) lines.push(indent(b, 1));
  lines.push(`</hashTree>`);
  return lines.join('\n');
}

function renderThreadGroupClosed(journey, threads, timing, samplerBlocks) {
  const lines = [];
  lines.push(`<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="${xml(journey.id)} (closed, w=${journey.weight})" enabled="true">`);
  lines.push(`  ${sp('ThreadGroup.on_sample_error', 'continue')}`);
  lines.push(`  <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">`);
  lines.push(`    ${bp('LoopController.continue_forever', true)}`);
  lines.push(`    ${sp('LoopController.loops', '-1')}`);
  lines.push(`  </elementProp>`);
  lines.push(`  ${sp('ThreadGroup.num_threads', String(threads))}`);
  lines.push(`  ${sp('ThreadGroup.ramp_time', String(Math.max(1, Math.round(timing.rampUp || 1))))}`);
  lines.push(`  ${bp('ThreadGroup.scheduler', true)}`);
  lines.push(`  ${sp('ThreadGroup.duration', String(Math.max(1, Math.round(timing.total))))}`);
  lines.push(`  ${sp('ThreadGroup.delay', '0')}`);
  lines.push(`</ThreadGroup>`);
  lines.push(`<hashTree>`);
  for (const b of samplerBlocks) lines.push(indent(b, 1));
  lines.push(`</hashTree>`);
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Test-plan-level config elements
// ---------------------------------------------------------------------------
function renderUserDefinedVars() {
  const vars = [
    ['PROTOCOL', '${__P(protocol,http)}'],
    ['HOST', '${__P(host,localhost)}'],
    ['PORT', '${__P(port,8080)}'],
  ];
  const lines = [];
  lines.push(`<Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">`);
  lines.push(`  <collectionProp name="Arguments.arguments">`);
  for (const [n, v] of vars) {
    lines.push(`    <elementProp name="${xml(n)}" elementType="Argument">`);
    lines.push(`      ${sp('Argument.name', n)}`);
    lines.push(`      ${sp('Argument.value', v)}`);
    lines.push(`      ${sp('Argument.metadata', '=')}`);
    lines.push(`    </elementProp>`);
  }
  lines.push(`  </collectionProp>`);
  lines.push(`</Arguments>`);
  lines.push(`<hashTree/>`);
  return lines.join('\n');
}

function renderHttpDefaults() {
  const lines = [];
  lines.push(`<ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults" enabled="true">`);
  lines.push(`  <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">`);
  lines.push(`    <collectionProp name="Arguments.arguments"/>`);
  lines.push(`  </elementProp>`);
  lines.push(`  ${sp('HTTPSampler.domain', '${HOST}')}`);
  lines.push(`  ${sp('HTTPSampler.port', '${PORT}')}`);
  lines.push(`  ${sp('HTTPSampler.protocol', '${PROTOCOL}')}`);
  lines.push(`</ConfigTestElement>`);
  lines.push(`<hashTree/>`);
  return lines.join('\n');
}

function renderCsvDataSet(ds) {
  const lines = [];
  lines.push(`<CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="CSV ${xml(ds.id)}" enabled="true">`);
  lines.push(`  ${sp('filename', `data/${ds.filename}`)}`);
  lines.push(`  ${sp('fileEncoding', 'UTF-8')}`);
  lines.push(`  ${sp('variableNames', ds.variableNames.join(','))}`);
  lines.push(`  ${bp('ignoreFirstLine', true)}`);
  lines.push(`  ${sp('delimiter', ',')}`);
  lines.push(`  ${bp('quotedData', true)}`);
  lines.push(`  ${bp('recycle', ds.recycle)}`);
  lines.push(`  ${bp('stopThread', false)}`);
  lines.push(`  ${sp('shareMode', 'shareMode.all')}`);
  lines.push(`</CSVDataSet>`);
  lines.push(`<hashTree/>`);
  return lines.join('\n');
}

function indent(block, n) {
  const pad = '  '.repeat(n);
  return block
    .split('\n')
    .map((l) => (l.length ? pad + l : l))
    .join('\n');
}

// ---------------------------------------------------------------------------
// Top-level generation
// ---------------------------------------------------------------------------
export function generateJmx(model, datasets) {
  const spec = model.spec;
  const warnings = [];
  const isOpen = spec.arrivalProfile.model === 'open';
  const expectedConcurrency =
    (spec.arrivalProfile.littlesLawCheck && spec.arrivalProfile.littlesLawCheck.expectedConcurrency) || null;
  const caps = spec.caps || {};

  let maxRate = 0;
  let totalThreads = 0;
  const threadGroups = [];

  for (const journey of spec.journeys) {
    const { driven, undriven } = partitionDrivableSteps(journey);
    for (const u of undriven) warnings.push(`jmeter: step "${u.id}" callType=${u.callType} is topology/baseline — not driven (G-X1)`);

    const { extractorsByStep, injectionsByStep } = buildCorrelations(journey);
    const ctx = { model, datasets, injectionsByStep, extractorsByStep, warnings };
    const samplerBlocks = driven.map((s) => renderSampler(s, ctx));

    const threads = threadCeiling(expectedConcurrency, journey.weight, caps);
    totalThreads += threads;

    let stages = spec.arrivalProfile.stages.slice();
    const steady = stages.length === 1 && (stages[0].shape === 'steady' || stages[0].shape == null);
    if (!steady) {
      const r = enforceRampDown(stages);
      if (r.appended) warnings.push(`jmeter: ramp-down synthesized for journey "${journey.id}" (model ended above zero)`);
      stages = r.stages;
    }
    const timing = classifyStages(stages);
    maxRate += stages.reduce((m, s) => Math.max(m, round4(Number(s.rate) * journey.weight)), 0);

    threadGroups.push(
      isOpen
        ? renderThreadGroupOpen(journey, stages, threads, timing, samplerBlocks, journey.weight)
        : renderThreadGroupClosed(journey, threads, timing, samplerBlocks)
    );
  }

  if (caps.maxVus != null && totalThreads > caps.maxVus) {
    warnings.push(`jmeter: total thread ceiling ${totalThreads} exceeds caps.maxVus=${caps.maxVus} across journeys (per-journey clamped; review concurrency split)`);
  }

  // test-plan body, in order
  const planChildren = [];
  planChildren.push(renderUserDefinedVars());
  planChildren.push(renderHttpDefaults());
  planChildren.push(renderHeaderManager([{ name: BAGGAGE_HEADER, value: BAGGAGE_VALUE }], 'Synthetic baggage (synthetic=true)'));
  for (const ds of Object.values(datasets)) planChildren.push(renderCsvDataSet(ds));
  for (const tg of threadGroups) planChildren.push(tg);

  const approval = model.status.approval || {};
  const header = [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<!-- AUTO-GENERATED by jmeter-synthesis (ISI-5656). Do not edit by hand. -->`,
    `<!-- Source model: ${model.metadata.name} rev ${model.status.revision}` +
      ` — approved by ${approval.decisionBy || '?'} at ${approval.decisionAt || '?'} -->`,
    `<!-- Requires jp@gc plugins: Concurrency Thread Group + Throughput Shaping Timer (open model). -->`,
    `<!-- synthetic=true is stamped on every request via the test-plan Header Manager (baggage). -->`,
    `<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">`,
  ];

  const lines = [];
  lines.push(...header);
  lines.push(`<hashTree>`);
  lines.push(`  <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="${xml(model.metadata.name)}" enabled="true">`);
  lines.push(`    ${sp('TestPlan.comments', `synthetic load — ${model.metadata.targetService || ''}`)}`);
  lines.push(`    ${bp('TestPlan.functional_mode', false)}`);
  lines.push(`    ${bp('TestPlan.serialize_threadgroups', false)}`);
  lines.push(`    <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">`);
  lines.push(`      <collectionProp name="Arguments.arguments"/>`);
  lines.push(`    </elementProp>`);
  lines.push(`    ${sp('TestPlan.user_define_classpath', '')}`);
  lines.push(`  </TestPlan>`);
  lines.push(`  <hashTree>`);
  for (const c of planChildren) lines.push(indent(c, 2));
  lines.push(`  </hashTree>`);
  lines.push(`</hashTree>`);
  lines.push(`</jmeterTestPlan>`);
  lines.push('');

  return { xml: lines.join('\n'), warnings, maxRate, totalThreads, isOpen };
}
