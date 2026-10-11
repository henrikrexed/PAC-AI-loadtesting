// lint.mjs — the Gatling renderer's OWN static check (V2a-equivalent, §3.3 Gate V2a).
//
// Full compilation (scalac / `gatling.sh`) is the EXECUTE-time gate and needs a JVM +
// the Gatling bundle, which this pure renderer does not shell out to. This lint is the
// fail-closed static smoke the renderer runs on its OWN output, mirroring k6's V2a:
//   1. brackets/parens/braces balance (strings + comments stripped)
//   2. the synthetic=true baggage header is set on the protocol (board requirement)
//   3. every referenced feeder file is present in the artifact set
//   4. no broken chain: every `#{c_...}` correlation ref has a matching `.saveAs`, and
//      every correlation `.saveAs` is referenced (G2 "fail fast on broken chain")
//   5. a ramping injection profile cools down to 0 (G3)
//   6. the peak injection rate is within caps.maxRps
//   7. randomSwitch journey-mix weights sum to <= 100

function stripScala(src) {
  // remove strings FIRST (so a `//` inside a URL string isn't mistaken for a
  // comment), then line comments.
  return src
    .replace(/"""[\s\S]*?"""/g, '""')
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/\/\/[^\n]*/g, '');
}

function balanced(src) {
  const s = stripScala(src);
  const pairs = { ')': '(', ']': '[', '}': '{' };
  const stack = [];
  for (const ch of s) {
    if (ch === '(' || ch === '[' || ch === '{') stack.push(ch);
    else if (pairs[ch]) {
      if (stack.pop() !== pairs[ch]) return false;
    }
  }
  return stack.length === 0;
}

function mk(id, title, pass, detail) {
  return { id, title, pass, detail };
}

/**
 * Lint a rendered Gatling artifact set against the model.
 *   render = { files:[{path,content}], ... }
 * Returns { pass, checks:[{id,title,pass,detail}] }.
 */
export function lintSimulation(render, model) {
  const checks = [];
  const files = render.files || [];
  const scala = files.find((f) => f.path.endsWith('.scala'));
  const src = (scala && scala.content) || '';
  const spec = (model && model.spec) || {};

  // 1. balance
  checks.push(mk('balance', 'brackets/braces balance', !!scala && balanced(src), scala ? '' : 'no .scala file emitted'));

  // 2. synthetic baggage header
  const hasSynthetic = /\.header\(\s*"baggage"\s*,\s*"synthetic=true"\s*\)/.test(src);
  checks.push(mk('synthetic', 'synthetic=true baggage header set on protocol', hasSynthetic, hasSynthetic ? '' : 'missing synthetic=true baggage header'));

  // 3. feeders present
  const feederRefs = [...src.matchAll(/jsonFile\("feeders\/([^"]+)\.json"\)/g)].map((m) => m[1]);
  const present = new Set(files.map((f) => f.path));
  const missingFeeders = feederRefs.filter((r) => !present.has(`gatling/feeders/${r}.json`));
  checks.push(mk('feeders', 'referenced feeders exist', missingFeeders.length === 0, missingFeeders.length ? `missing: ${missingFeeders.join(', ')}` : `${feederRefs.length} feeder(s)`));

  // 4. chain closure
  const refs = new Set([...src.matchAll(/#\{(c_[A-Za-z0-9_]+)\}/g)].map((m) => m[1]));
  const saves = new Set([...src.matchAll(/\.saveAs\("(c_[A-Za-z0-9_]+)"\)/g)].map((m) => m[1]));
  const danglingRef = [...refs].filter((r) => !saves.has(r));
  const unusedSave = [...saves].filter((s) => !refs.has(s));
  const chainOk = danglingRef.length === 0 && unusedSave.length === 0;
  checks.push(mk('chain', 'correlation chain is closed (no dangling saveAs/ref)', chainOk,
    chainOk ? `${saves.size} correlation(s)` : `dangling refs: [${danglingRef.join(', ')}] unused saves: [${unusedSave.join(', ')}]`));

  // 5. ramp-down to zero (only for ramping profiles)
  const stages = (spec.arrivalProfile && spec.arrivalProfile.stages) || [];
  const anyRamp = stages.some((s) => s.shape && s.shape !== 'steady' && s.shape !== 'plateau' && s.shape !== 'constant');
  const rampDownOk = !anyRamp || /\.to\(0(?:\.0)?\)\.during/.test(src);
  checks.push(mk('rampdown', 'ramping profile cools down to 0', rampDownOk, rampDownOk ? '' : 'no ramp .to(0) found'));

  // 6. caps
  const caps = spec.caps || {};
  const peak = stages.reduce((m, s) => Math.max(m, Number(s.rate) || 0), 0);
  const capOk = caps.maxRps == null || peak <= caps.maxRps + 1e-9;
  checks.push(mk('caps', 'peak injection rate within caps.maxRps', capOk, capOk ? `peak=${peak} maxRps=${caps.maxRps ?? '∞'}` : `peak ${peak} > maxRps ${caps.maxRps}`));

  // 7. randomSwitch weights
  const pctVals = [...src.matchAll(/^\s*([0-9]+(?:\.[0-9]+)?)\s*->\s*/gm)].map((m) => parseFloat(m[1]));
  const sum = pctVals.reduce((a, b) => a + b, 0);
  const weightsOk = pctVals.length === 0 || sum <= 100 + 1e-6;
  checks.push(mk('weights', 'randomSwitch journey-mix weights sum <= 100', weightsOk, `sum=${Math.round(sum * 1e4) / 1e4}`));

  return { pass: checks.every((c) => c.pass), checks };
}
