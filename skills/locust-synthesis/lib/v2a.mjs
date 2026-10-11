// v2a.mjs — the Locust renderer's OWN static check (V2a-equivalent, §3.3 "Gate
// V2a"). Fail-closed: any failing check fails the gate. The "tool's own checker"
// for a Python/Locust script is the CPython compiler: `python3 -m py_compile`
// parses the locustfile + every helper exactly as Locust will import them (Locust
// has no standalone lint/--check mode). On top of that we assert the renderer's
// semantic invariants against the model: synthetic=true on every request, feeders
// present + well-formed, chain fail-fast guards for dependsOn steps, the open-model
// LoadTestShape, and the user-ceiling within caps.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const HTTP_CALL_RE = /self\.client\.(get|post|put|patch|delete|head|options|request)\s*\(/g;

export function v2aCheck({ model, source, scriptPath, outDir, shape }) {
  const checks = [];
  const spec = model.spec;
  const libDir = path.join(outDir, 'locust', 'lib');

  checks.push(parseCheck(scriptPath, libDir));
  checks.push(baggageCheck(source, libDir));
  checks.push(feedersCheck(model, outDir));
  checks.push(correlationCheck(spec, source));
  checks.push(shapeCheck(spec, shape, source));
  checks.push(capsCheck(spec, shape));
  checks.push(committedCheck(scriptPath, outDir));

  // Approval is ADVISORY here: render() deliberately emits an unapproved model for
  // human PREVIEW, so it does not fail the technical static gate. The hard V1 gate
  // lives at the SYNTHESIZE/EXECUTE boundary; this flag surfaces it for VALIDATE.
  const approval = approvalCheck(model);
  checks.push(approval);

  const pass = checks.filter((c) => c.id !== 'approval').every((c) => c.pass);
  return { pass, approved: approval.pass, checks };
}

/** CPython compile — the Locust runtime's own parser. */
function parseCheck(scriptPath, libDir) {
  const py = pythonBin();
  if (!py) return mk('parse', 'script compiles (python -m py_compile)', false, 'python3 not found on PATH');
  const targets = [scriptPath];
  for (const h of ['synthetic.py', 'chain.py', 'think.py', 'pool.py', 'shape.py']) {
    const f = path.join(libDir, h);
    if (existsSync(f)) targets.push(f);
  }
  try {
    execFileSync(py, ['-m', 'py_compile', ...targets], { stdio: 'pipe' });
    return mk('parse', 'script compiles (python -m py_compile)', true, `${targets.length} files compile`);
  } catch (e) {
    const msg = (e.stderr && e.stderr.toString()) || e.message;
    return mk('parse', 'script compiles (python -m py_compile)', false, msg.split('\n').slice(0, 4).join(' '));
  }
}

function pythonBin() {
  for (const bin of ['python3', 'python']) {
    try {
      execFileSync(bin, ['--version'], { stdio: 'pipe' });
      return bin;
    } catch (_e) {
      /* try next */
    }
  }
  return null;
}

function baggageCheck(source, libDir) {
  const lines = source.split('\n');
  const offenders = [];
  for (const line of lines) {
    HTTP_CALL_RE.lastIndex = 0;
    if (HTTP_CALL_RE.test(line) && !line.includes('synthetic_headers') && !line.includes('headers=_headers')) {
      offenders.push(line.trim());
    }
  }
  let helperOk = false;
  const helper = path.join(libDir, 'synthetic.py');
  if (existsSync(helper)) helperOk = readFileSync(helper, 'utf8').includes('synthetic=true');
  const pass = offenders.length === 0 && helperOk;
  const detail = pass
    ? 'all requests carry synthetic=true (synthetic_headers)'
    : offenders.length
      ? `requests missing synthetic_headers: ${offenders.length}`
      : 'synthetic helper missing or does not set synthetic=true';
  return mk('baggage', 'every request carries baggage synthetic=true', pass, detail);
}

function feedersCheck(model, outDir) {
  const pools = (model.spec && model.spec.payloads) || {};
  const problems = [];
  for (const [id, pspec] of Object.entries(pools)) {
    const file = path.join(outDir, 'locust', 'feeders', `${id}.json`);
    if (!existsSync(file)) {
      problems.push(`${id}: feeder missing`);
      continue;
    }
    let pool;
    try {
      pool = JSON.parse(readFileSync(file, 'utf8'));
    } catch (_e) {
      problems.push(`${id}: invalid JSON`);
      continue;
    }
    if (pspec.cacheProfile) {
      if (pool.kind !== 'cache-key') problems.push(`${id}: expected cache-key feeder`);
      if (!Array.isArray(pool.keys)) problems.push(`${id}: no keys[]`);
      if (!Array.isArray(pool.cdf) || pool.cdf.length !== (pool.keys || []).length) {
        problems.push(`${id}: cdf/keys length mismatch`);
      }
    } else if (pool.kind !== 'record' || !Array.isArray(pool.records)) {
      problems.push(`${id}: expected record feeder with records[]`);
    }
  }
  const pass = problems.length === 0;
  return mk('feeders', 'referenced feeders exist and match specs', pass, pass ? `${Object.keys(pools).length} feeders OK` : problems.join('; '));
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
      // the generated step must guard the chain with require_value(..., "<stepId>", ...)
      if (!source.includes(`require_value(extract(`) || !source.includes(`, '${s.id}', `)) {
        problems.push(`${j.id}/${s.id}: missing fail-fast guard`);
      }
    }
  }
  const pass = problems.length === 0;
  return mk('correlation', 'dependsOn steps extract + fail-fast on null', pass, pass ? 'all chains guarded' : problems.join('; '));
}

function shapeCheck(spec, shape, source) {
  const problems = [];
  if (!source.includes('class GeneratedShape(StagedShape)')) problems.push('no GeneratedShape');
  if (!shape || !Array.isArray(shape.stages) || shape.stages.length === 0) problems.push('empty stage table');
  else {
    // ramping profiles must terminate at 0 users (G3)
    const steady =
      spec.arrivalProfile.stages.length === 1 &&
      (spec.arrivalProfile.stages[0].shape === 'steady' || spec.arrivalProfile.stages[0].shape == null);
    if (!steady) {
      const last = shape.stages[shape.stages.length - 1];
      if (!last || last.users !== 0) problems.push('ramping schedule does not end at 0 users');
    }
  }
  const pass = problems.length === 0;
  return mk('shape', 'LoadTestShape present (open-arrival approximation, G-O1)', pass, pass ? `${shape.stages.length} stages` : problems.join('; '));
}

function capsCheck(spec, shape) {
  const caps = spec.caps || {};
  const problems = [];
  if (caps.maxVus != null && shape.peakUsers > caps.maxVus) {
    problems.push(`peak users ${shape.peakUsers} > caps.maxVus ${caps.maxVus}`);
  }
  const pass = problems.length === 0;
  return mk('caps', 'peak user ceiling <= caps.maxVus', pass, pass ? `peak users ${shape.peakUsers}` : problems.join('; '));
}

function committedCheck(scriptPath, outDir) {
  const required = [
    scriptPath,
    path.join(outDir, 'locust', 'lib', 'synthetic.py'),
    path.join(outDir, 'locust', 'lib', 'chain.py'),
    path.join(outDir, 'locust', 'lib', 'think.py'),
    path.join(outDir, 'locust', 'lib', 'pool.py'),
    path.join(outDir, 'locust', 'lib', 'shape.py'),
    path.join(outDir, 'locust', 'requirements.txt'),
  ];
  const missing = required.filter((f) => !existsSync(f));
  const pass = missing.length === 0;
  return mk('committed', 'locustfile + helpers present on disk', pass, pass ? `${required.length} files present` : `missing: ${missing.join(', ')}`);
}

/**
 * Approval visibility (soft). render() still emits for an unapproved model so a
 * human can PREVIEW it, but the static check records whether the V1 gate would
 * pass. Hard enforcement lives at the SYNTHESIZE boundary — this surfaces it.
 */
function approvalCheck(model) {
  const a = model.status && model.status.approval;
  const ok = !!a && a.decision === 'approved' && a.revision === model.status.revision;
  return mk('approval', 'model approved for its current revision (V1)', ok, ok ? 'approved' : 'NOT approved — preview only (SYNTHESIZE gate blocks EXECUTE)');
}

function mk(id, title, pass, detail) {
  return { id, title, pass, detail };
}
