// codegen.mjs — model -> locustfile.py generation (ISI-5657, §3.3 / research §4.1).
//
// Emits ONE locustfile with: one HttpUser whose @task(weight) methods ARE the
// journeys (journey mix via @task weights, G3-closed); each journey runs its
// steps in order inline (chaining via a local `responses` dict, G2); open arrival
// is approximated by a StagedShape computed from Little's Law + constant_pacing
// (G-O1); synthetic=true baggage rides every request via synthetic_headers()
// (P4/§7.7); G4 cache-avoidance via the pre-generated feeders (pool.py).
//
// The Python it emits is deterministic (no Date/random at codegen) so two renders
// of the same model are byte-identical (acceptance harness, §4.3).

import { enforceRampDown, durationToSeconds } from '../../k6-synthesis/lib/arrival.mjs';
import {
  resolveRequest,
  resolveFieldTarget,
  methodHasBody,
  partitionDrivableSteps,
} from '../../renderer-kit/lib/model-access.mjs';

const BODYLESS_DEFAULT_BASE = 'http://localhost:8080';

/** Python identifier from an arbitrary id (journey/step). */
function pyIdent(id) {
  const safe = String(id).replace(/[^A-Za-z0-9_]/g, '_');
  return /^[0-9]/.test(safe) ? `j_${safe}` : safe;
}

/** PascalCase class name, e.g. "shop-checkout" -> "ShopCheckoutUser". */
function toClassName(s, suffix) {
  return (
    String(s)
      .split(/[^A-Za-z0-9]+/)
      .filter(Boolean)
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join('') + suffix
  );
}

/** Python single-quoted string literal. */
function pyStr(s) {
  return `'${String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
}

/** A dict literal containing only strings/numbers is valid Python as JSON. */
function pyDict(obj) {
  return JSON.stringify(obj);
}

/** Valid Python key for a dict literal. */
function pyKey(k) {
  return pyStr(k);
}

// ---- Little's-Law user schedule (open-arrival approximation, G-O1) ----

/**
 * Build the StagedShape stage table + the per-user pacing seconds.
 * Returns { stages, pacingSec, peakUsers, warnings }.
 *   open model  -> users_stage = round(expectedConcurrency * rate/peakRate)
 *   closed model-> users_stage = round(rate)  (rate already means users/VUs)
 * Clamps peak users to caps.maxVus.
 */
function buildShape(spec) {
  const warnings = [];
  const ap = spec.arrivalProfile;
  const isOpen = ap.model === 'open';
  const caps = spec.caps || {};

  const steady =
    ap.stages.length === 1 && (ap.stages[0].shape === 'steady' || ap.stages[0].shape == null);
  const stages = steady ? ap.stages.slice() : enforceRampDown(ap.stages).stages;
  if (!steady && enforceRampDown(ap.stages).appended) {
    warnings.push('ramp-down stage synthesized (model ended above zero)');
  }

  const peakRate = ap.stages.reduce((m, s) => Math.max(m, Number(s.rate) || 0), 0);
  const expected =
    (ap.littlesLawCheck && Number(ap.littlesLawCheck.expectedConcurrency)) || null;
  // mean service time (s) from Little's Law: W = L / lambda.
  const meanServiceSec = expected != null && peakRate > 0 ? expected / peakRate : null;

  function usersFor(rate) {
    if (!isOpen) return Math.max(0, Math.round(Number(rate) || 0));
    if (expected != null && peakRate > 0) {
      return Math.max(0, Math.round((expected * Number(rate)) / peakRate));
    }
    // no Little's-Law evidence: fall back to 1 user per iteration/s target.
    return Math.max(0, Math.round(Number(rate) || 0));
  }

  let peakUsers = 0;
  let acc = 0;
  const table = [];
  let prevUsers = 0;
  for (const s of stages) {
    const dur = durationToSeconds(s.duration);
    acc += dur;
    let users = usersFor(s.rate);
    if (caps.maxVus != null && users > caps.maxVus) {
      users = caps.maxVus;
      warnings.push(`stage users clamped to caps.maxVus=${caps.maxVus}`);
    }
    peakUsers = Math.max(peakUsers, users);
    // spawn rate approximates ramping |delta users| over the window (min 0.1/s).
    const delta = Math.abs(users - prevUsers);
    const spawn = Math.max(0.1, round4((delta || users || 1) / Math.max(1, dur)));
    table.push({ end_s: round4(acc), users, spawn_rate: spawn });
    prevUsers = users;
  }

  const pacingSec = isOpen && meanServiceSec != null ? round4(Math.max(0.001, meanServiceSec)) : 1.0;
  return { stages: table, pacingSec, peakUsers, isOpen, meanServiceSec, warnings };
}

function round4(n) {
  return Math.round(n * 1e4) / 1e4;
}

// ---- URL / body / header rendering (mirrors k6 correlate.mjs, Python output) ----

/** Replace a {token} / :token / [token] path placeholder with a Python f-string slot. */
function tokenRe(token) {
  return new RegExp(`\\{${escapeRe(token)}\\}|\\[${escapeRe(token)}\\]|:${escapeRe(token)}(?=/|$)`);
}
function soleToken(path) {
  const curly = path.match(/\{([^}]+)\}/g);
  if (curly && curly.length === 1) return curly[0].slice(1, -1);
  const square = path.match(/\[([^\]]+)\]/g);
  if (square && square.length === 1) return square[0].slice(1, -1);
  return null;
}
function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Build the Python URL expression. path_param injections + a single cache-key
 * pool value fill path tokens; query_param injections append a query string.
 * Returns a Python string/f-string expression. Literal braces are escaped.
 */
function renderUrlPy(pathTemplate, injections, poolKeyExpr) {
  let out = pathTemplate;
  const exprs = [];
  // Replace each resolved path token with a unique sentinel " <idx> " and stash
  // its Python expression. Sentinels carry no { / [ so a later soleToken() still
  // finds a remaining real token and literal-brace escaping can't collide.
  const sub = (tok, expr) => {
    const re = tokenRe(tok);
    if (!re.test(out)) return false;
    out = out.replace(re, ` ${exprs.length} `);
    exprs.push(expr);
    return true;
  };
  for (const j of injections.filter((i) => i.into === 'path_param')) sub(j.as, j.expr);
  if (poolKeyExpr) {
    const tok = soleToken(out);
    if (tok) sub(tok, poolKeyExpr);
  }
  const query = injections.filter((i) => i.into === 'query_param');
  if (exprs.length === 0 && query.length === 0) return pyStr(out);

  // escape literal braces, then swap each sentinel for its {expr} f-string slot
  let body = out.replace(/\{/g, '{{').replace(/\}/g, '}}');
  body = body.replace(/ (\d+) /g, (_m, idx) => `{${exprs[Number(idx)]}}`);
  if (query.length) {
    const sep = body.includes('?') ? '&' : '?';
    body += sep + query.map((j) => `${j.as}={${j.expr}}`).join('&');
  }
  return `f'${body.replace(/'/g, "\\'")}'`;
}

/**
 * Render correlation extraction lines + the injection list for one step.
 * Returns { lines, injections }. Each injection = { into, as, expr } where expr
 * is a Python variable name holding the (require_value-guarded) correlated value.
 */
function renderCorrelations(step, indent) {
  const lines = [];
  const injections = [];
  (step.correlates || []).forEach((c, i) => {
    const v = `corr${i}`;
    const spec = pyDict({ from: c.extract.from, path: c.extract.path });
    lines.push(
      `${indent}${v} = require_value(extract(responses.get(${pyStr(c.sourceStepId)}), ${spec}), ${pyStr(
        step.id
      )}, ${pyStr(c.inject.as)})`
    );
    injections.push({ into: c.inject.into, as: c.inject.as, expr: v });
  });
  return { lines, injections };
}

/** Render the request body dict expression (Python), or null for bodyless methods. */
function renderBodyPy(payloadRecordExpr, injections) {
  const bodyInj = injections.filter((j) => j.into === 'body_field');
  if (!payloadRecordExpr && bodyInj.length === 0) return null;
  const base = payloadRecordExpr ? `dict(${payloadRecordExpr})` : '{}';
  if (bodyInj.length === 0) return base;
  const fields = bodyInj.map((j) => `${pyKey(j.as)}: ${j.expr}`).join(', ');
  return `{**${base}, ${fields}}`;
}

/** Render header injections as a Python dict expression passed to synthetic_headers(). */
function renderHeaderInjectionsPy(injections) {
  const hdr = injections.filter((j) => j.into === 'header');
  if (hdr.length === 0) return null;
  const fields = hdr.map((j) => `${pyKey(j.as)}: ${j.expr}`).join(', ');
  return `{${fields}}`;
}

const PY_METHODS = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options']);
function pyClientMethod(method) {
  const m = String(method || 'GET').toLowerCase();
  return PY_METHODS.has(m) ? m : 'request';
}

/** Render one journey step (HTTP) as Python statements inside the @task body. */
function renderStep(step, poolKinds, warnings) {
  const ind = '        '; // 8 spaces: inside a method body
  const req = resolveRequest(step);
  const { lines: corrLines, injections } = renderCorrelations(step, ind);

  let poolKeyExpr = null;
  let payloadRecordExpr = null;
  if (req.bodyPayloadRef) {
    const kind = poolKinds[req.bodyPayloadRef];
    const ref = `POOL_${pyIdent(req.bodyPayloadRef)}`;
    if (kind === 'cache-key') poolKeyExpr = `pick_key(${ref}, random.random())`;
    else if (kind === 'record') payloadRecordExpr = `pick_record(${ref}, random.random())`;
  }

  const hasBody = methodHasBody(req.method);
  const url = renderUrlPy(req.pathTemplate, injections, hasBody ? null : poolKeyExpr);
  if (!hasBody && poolKeyExpr && !url.startsWith('f')) {
    warnings.push(
      `step ${step.id}: cache-key pool ${req.bodyPayloadRef} has no path token to bind (feeder generated but unbound)`
    );
  }
  const bodyExpr = hasBody ? renderBodyPy(payloadRecordExpr, injections) : null;
  const headerInj = renderHeaderInjectionsPy(injections);
  const headerArg = headerInj ? `synthetic_headers(${headerInj})` : 'synthetic_headers()';

  const method = pyClientMethod(req.method);
  const name = pyStr(step.id);
  const lines = [];
  lines.push(`${ind}# step ${step.id} — ${req.method} ${req.pathTemplate}`);
  for (const l of corrLines) lines.push(l);
  lines.push(`${ind}_headers = ${headerArg}`);
  lines.push(`${ind}_url = ${url}`);
  if (hasBody) {
    const body = bodyExpr || '{}';
    lines.push(`${ind}_headers.setdefault('Content-Type', 'application/json')`);
    lines.push(
      `${ind}with self.client.${method}(_url, json=${body}, headers=_headers, name=${name}, catch_response=True) as _res:`
    );
  } else {
    lines.push(
      `${ind}with self.client.${method}(_url, headers=_headers, name=${name}, catch_response=True) as _res:`
    );
  }
  lines.push(`${ind}    _res.success() if (0 < (_res.status_code or 0) < 500) else _res.failure(f'status {_res.status_code}')`);
  lines.push(`${ind}    responses[${name}] = _res`);
  if (step.thinkTime) {
    lines.push(`${ind}time.sleep(think_seconds(${pyDict(step.thinkTime)}, random.random()))`);
  }
  return lines.join('\n');
}

/** Render one journey as an @task(weight) method on the User. */
function renderJourney(journey, poolKinds, warnings) {
  const weight = Math.max(1, Math.round((journey.weight || 0) * 100));
  const { driven, undriven } = partitionDrivableSteps(journey);
  for (const s of undriven) {
    warnings.push(`journey ${journey.id}: non-http step ${s.id} (${s.callType}) omitted (G-X1)`);
  }
  const lines = [];
  lines.push(`    @task(${weight})  # journey "${journey.id}" weight ${journey.weight}`);
  lines.push(`    def ${pyIdent(journey.id)}(self):`);
  lines.push(`        self.client.cookies.clear()  # fresh user per journey iteration (G2 session isolation)`);
  lines.push(`        responses = {}`);
  if (!driven.length) {
    lines.push('        pass  # no drivable HTTP edge steps');
    return lines.join('\n');
  }
  for (const s of driven) lines.push(renderStep(s, poolKinds, warnings));
  return lines.join('\n');
}

/**
 * Generate the locustfile source + metadata.
 * Returns { source, shape, warnings, usedPools }.
 */
export function generateLocustfile(model, poolKinds) {
  const spec = model.spec;
  const warnings = [];
  const shape = buildShape(spec);
  warnings.push(...shape.warnings);

  const name = (model.metadata && model.metadata.name) || 'workload';
  const rev = (model.status && model.status.revision) ?? '?';
  const approval = model.status && model.status.approval;
  const approvalNote = approval
    ? `approved by ${approval.decisionBy} at ${approval.decisionAt}`
    : 'NOT APPROVED — render for preview only; SYNTHESIZE enforces the V1 gate';

  const usedPools = new Set();
  for (const j of spec.journeys) for (const s of j.steps || []) {
    const ref = resolveRequest(s).bodyPayloadRef;
    if (ref) usedPools.add(ref);
  }

  const header = [
    `# AUTO-GENERATED by locust-synthesis (ISI-5657). Do not edit by hand.`,
    `# Source model: ${name} rev ${rev} — ${approvalNote}`,
    `#`,
    `# Run: locust -f ${name}.py --host http://<target>`,
    `#      (user count + ramp are driven by GeneratedShape; no -u/-r needed)`,
  ];
  const report = capabilityNotes(spec);
  if (report.length) {
    header.push('#');
    header.push('# CAPABILITY REPORT (approximations applied — confirm at VALIDATE):');
    for (const u of report) header.push(`#   - ${u}`);
  }

  const imports = [
    ``,
    `import os`,
    `import time`,
    `import random`,
    ``,
    `from locust import HttpUser, task, constant_pacing`,
    ``,
    `from lib.synthetic import synthetic_headers, instrument_otel`,
    `from lib.chain import extract, require_value, BrokenChainError`,
    `from lib.think import think_seconds`,
    `from lib.pool import load_feeder, pick_key, pick_record`,
    `from lib.shape import StagedShape`,
    ``,
    `# OTel client-span emission (best-effort; baggage synthetic=true rides every`,
    `# request header regardless). Enabled iff the SDK is installed and`,
    `# OTEL_EXPORTER_OTLP_ENDPOINT is set — see lib/synthetic.py / requirements.txt.`,
    `instrument_otel()`,
    ``,
    `_FEEDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feeders')`,
  ];
  for (const ref of usedPools) {
    imports.push(`POOL_${pyIdent(ref)} = load_feeder(os.path.join(_FEEDER_DIR, ${pyStr(`${ref}.json`)}))`);
  }

  // StagedShape subclass (open-arrival approximation / closed user schedule, G-O1/G3)
  const shapeStageLiteral = shape.stages
    .map((s) => `        {'end_s': ${s.end_s}, 'users': ${s.users}, 'spawn_rate': ${s.spawn_rate}},`)
    .join('\n');
  const shapeBlock = [
    ``,
    ``,
    `class GeneratedShape(StagedShape):`,
    `    # ${shape.isOpen ? 'open arrival approximated via Little\'s Law + constant_pacing (G-O1)' : 'closed model: user count = concurrency per stage'}`,
    `    stages = [`,
    shapeStageLiteral,
    `    ]`,
  ];

  const userClass = [
    ``,
    ``,
    `class ${toClassName(name, 'User')}(HttpUser):`,
    `    host = os.environ.get('TARGET_HOST', ${pyStr(BODYLESS_DEFAULT_BASE)})`,
    `    # per-task pacing approximates the open-model arrival rate (${shape.isOpen ? 'G-O1' : 'closed'});`,
    `    # each user issues ~1 journey / ${shape.pacingSec}s.`,
    `    wait_time = constant_pacing(${shape.pacingSec})`,
    ``,
  ];
  const journeyFns = spec.journeys.map((j) => renderJourney(j, poolKinds, warnings));

  const source =
    [...header, ...imports, ...shapeBlock, ...userClass].join('\n') +
    '\n' +
    journeyFns.join('\n\n') +
    '\n';

  return { source, shape, warnings, usedPools: [...usedPools] };
}

/** Human-readable capability notes for the file header (parallels supports()). */
function capabilityNotes(spec) {
  const notes = [];
  if (spec.arrivalProfile && spec.arrivalProfile.model === 'open') {
    notes.push('arrivalProfile.model=open -> LoadTestShape + per-task pacing (Little\'s Law)');
  }
  let empirical = false;
  let bodyHtml = false;
  const undriven = new Set();
  for (const j of spec.journeys || []) {
    for (const s of j.steps || []) {
      if (s.thinkTime && s.thinkTime.distribution === 'empirical') empirical = true;
      if (s.callType && s.callType !== 'http') undriven.add(s.callType);
      for (const c of s.correlates || []) if (c.extract && c.extract.from === 'body_html') bodyHtml = true;
    }
  }
  if (empirical) notes.push('thinkTime.distribution=empirical -> sampled list in think.py');
  if (bodyHtml) notes.push('correlates.extract.from=body_html -> marker/regex extraction in chain.py');
  if (undriven.size) notes.push(`callType in {${[...undriven].sort().join(',')}} omitted (topology/baseline only)`);
  return notes;
}
