// v2a.mjs — V2a static checker (methodology §3.3 "Exit criteria — Gate V2a").
// Validates generated scripts against the model BEFORE EXECUTE. Fail-closed:
// any failing check marks the whole gate failed.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const HTTP_CALL_RE = /http\.(get|post|put|patch|del|head|options|request)\s*\(/g;

/**
 * Run V2a against a generated artifact set.
 *   args = { model, source, scriptPath, outDir, options, maxRate }
 * Returns { pass, checks: [{ id, title, pass, detail }] }.
 */
export function v2aCheck({ model, source, scriptPath, outDir, options, maxRate }) {
  const checks = [];
  const spec = model.spec;

  // 1. parse succeeds (k6 inspect when available, else node --check)
  checks.push(parseCheck(scriptPath));

  // 2. every request carries baggage synthetic=true
  checks.push(baggageCheck(source, outDir));

  // 3. referenced payload pools exist and match specs
  checks.push(poolsCheck(model, outDir));

  // 4. declared max rate / VU <= caps
  checks.push(capsCheck(spec, options, maxRate));

  // 5. every dependsOn step produces a correlates extract + fail-fast guard
  checks.push(correlationCheck(spec, source));

  // 6. all ramping scenarios end with a ramp-down reaching 0
  checks.push(rampDownCheck(options));

  // 7. scripts + helpers present on disk (tests are code)
  checks.push(committedCheck(scriptPath, outDir, model));

  const pass = checks.every((c) => c.pass);
  return { pass, checks };
}

function parseCheck(scriptPath) {
  let engine = 'node --check';
  let bin = 'node';
  let argv = ['--check', scriptPath];
  if (hasK6()) {
    engine = 'k6 inspect';
    bin = 'k6';
    argv = ['inspect', scriptPath];
  }
  try {
    execFileSync(bin, argv, { stdio: 'pipe' });
    return mk('parse', `script parses (${engine})`, true, `${engine} OK`);
  } catch (e) {
    const msg = (e.stderr && e.stderr.toString()) || e.message;
    return mk('parse', `script parses (${engine})`, false, msg.split('\n').slice(0, 3).join(' '));
  }
}

function hasK6() {
  try {
    execFileSync('k6', ['version'], { stdio: 'pipe' });
    return true;
  } catch (_e) {
    return false;
  }
}

function baggageCheck(source, outDir) {
  // every http.* request statement must route through syntheticParams(...)
  const lines = source.split('\n');
  const offenders = [];
  for (const line of lines) {
    HTTP_CALL_RE.lastIndex = 0;
    if (HTTP_CALL_RE.test(line) && !line.includes('syntheticParams(')) offenders.push(line.trim());
  }
  // and the helper actually encodes synthetic=true
  let helperOk = false;
  const helper = path.join(outDir, 'k6', 'lib', 'baggage.js');
  if (existsSync(helper)) helperOk = readFileSync(helper, 'utf8').includes("synthetic=true");
  const pass = offenders.length === 0 && helperOk;
  const detail = pass
    ? 'all requests route through syntheticParams() (baggage synthetic=true)'
    : offenders.length
      ? `requests missing syntheticParams: ${offenders.length}`
      : 'baggage helper missing or does not set synthetic=true';
  return mk('baggage', 'every request carries baggage synthetic=true', pass, detail);
}

function poolsCheck(model, outDir) {
  const pools = (model.spec && model.spec.payloads) || {};
  const problems = [];
  for (const [id, pspec] of Object.entries(pools)) {
    const file = path.join(outDir, 'payloads', `${id}.json`);
    if (!existsSync(file)) {
      problems.push(`${id}: file missing`);
      continue;
    }
    let pool;
    try {
      pool = JSON.parse(readFileSync(file, 'utf8'));
    } catch (e) {
      problems.push(`${id}: invalid JSON`);
      continue;
    }
    if (pspec.cacheProfile) {
      const K = pspec.cacheProfile.keyCardinality;
      if (pool.kind !== 'cache-key') problems.push(`${id}: expected cache-key pool`);
      if (!Array.isArray(pool.keys)) problems.push(`${id}: no keys[]`);
      else if (K != null && pool.keys.length !== K) problems.push(`${id}: keys=${pool.keys.length} != keyCardinality=${K}`);
      if (!Array.isArray(pool.cdf) || pool.cdf.length !== (pool.keys || []).length) problems.push(`${id}: cdf/keys length mismatch`);
    } else if (pool.kind !== 'record' || !Array.isArray(pool.records)) {
      problems.push(`${id}: expected record pool with records[]`);
    }
  }
  const pass = problems.length === 0;
  return mk('pools', 'referenced payload pools exist and match specs', pass, pass ? `${Object.keys(pools).length} pools OK` : problems.join('; '));
}

function capsCheck(spec, options, maxRate) {
  const caps = spec.caps || {};
  const problems = [];
  if (caps.maxRps != null && maxRate > caps.maxRps + 1e-6) {
    problems.push(`declared max rate ${round(maxRate)} > caps.maxRps ${caps.maxRps}`);
  }
  if (caps.maxVus != null) {
    for (const [id, sc] of Object.entries(options.scenarios || {})) {
      const vus = sc.maxVUs != null ? sc.maxVUs : maxStageTarget(sc);
      if (vus != null && vus > caps.maxVus) problems.push(`scenario ${id} VUs ${vus} > caps.maxVus ${caps.maxVus}`);
    }
  }
  const pass = problems.length === 0;
  return mk('caps', 'declared max rate/VU <= caps', pass, pass ? 'within caps' : problems.join('; '));
}

function maxStageTarget(sc) {
  if (Array.isArray(sc.stages)) return sc.stages.reduce((m, s) => Math.max(m, Number(s.target) || 0), 0);
  if (sc.vus != null) return sc.vus;
  return null;
}

function correlationCheck(spec, source) {
  const problems = [];
  for (const j of spec.journeys) {
    for (const s of j.steps || []) {
      const hasDep = Array.isArray(s.dependsOn) && s.dependsOn.length > 0;
      if (!hasDep) continue;
      const hasCorr = Array.isArray(s.correlates) && s.correlates.length > 0;
      if (!hasCorr) {
        problems.push(`${j.id}/${s.id}: dependsOn without correlates`);
        continue;
      }
      // generated step must contain the fail-fast guard for this step
      const guard = `broken chain at step=${s.id}:`;
      if (!source.includes(guard)) problems.push(`${j.id}/${s.id}: missing fail-fast guard`);
    }
  }
  const pass = problems.length === 0;
  return mk('correlation', 'dependsOn steps extract + fail-fast on null', pass, pass ? 'all chains guarded' : problems.join('; '));
}

function rampDownCheck(options) {
  const problems = [];
  for (const [id, sc] of Object.entries(options.scenarios || {})) {
    if (String(sc.executor).startsWith('ramping-')) {
      const stages = sc.stages || [];
      const last = stages[stages.length - 1];
      if (!last || Number(last.target) !== 0) problems.push(`scenario ${id} does not end at 0`);
    }
  }
  const pass = problems.length === 0;
  return mk('rampdown', 'ramping scenarios end with ramp-down to 0', pass, pass ? 'ramp-down present' : problems.join('; '));
}

function committedCheck(scriptPath, outDir, model) {
  const required = [
    scriptPath,
    path.join(outDir, 'k6', 'lib', 'baggage.js'),
    path.join(outDir, 'k6', 'lib', 'chain.js'),
    path.join(outDir, 'k6', 'lib', 'session.js'),
    path.join(outDir, 'k6', 'lib', 'pool.js'),
    path.join(outDir, 'k6', 'lib', 'think.js'),
  ];
  const missing = required.filter((f) => !existsSync(f));
  const pass = missing.length === 0;
  return mk('committed', 'scripts + helpers present on disk', pass, pass ? `${required.length} files present` : `missing: ${missing.join(', ')}`);
}

function mk(id, title, pass, detail) {
  return { id, title, pass, detail };
}
function round(n) {
  return Math.round(n * 100) / 100;
}
