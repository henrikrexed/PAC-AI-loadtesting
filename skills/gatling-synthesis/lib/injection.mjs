// injection.mjs — arrivalProfile -> Gatling injection profile (G3, research §4.1).
//
// Open arrival model  -> rate injection (constantUsersPerSec / rampUsersPerSec).
// Closed arrival model -> concurrency injection (constantConcurrentUsers /
//   rampConcurrentUsers), with the max-concurrent ceiling from Little's Law.
//
// `shape` is authoritative (G-D1): a ramping stage ramps from the PREVIOUS stage's
// end rate; the first ramping stage starts at 0; a ramp_down reaches 0. A terminal
// ramp-down to 0 is the EXECUTE-time expectation — the lint (V2a-equivalent) fails
// closed if a ramping profile does not end at zero.

/** Map a model duration string ('5m','30s','500ms','1h','179m') to a Gatling Scala duration. */
export function scalaDuration(d) {
  if (typeof d === 'number') return `${d}.seconds`;
  const m = /^(\d+(?:\.\d+)?)(ms|s|m|h)$/.exec(String(d).trim());
  if (!m) throw new Error(`unparseable duration: ${d}`);
  const unit = { ms: 'milliseconds', s: 'seconds', m: 'minutes', h: 'hours' }[m[2]];
  return `${m[1]}.${unit}`;
}

/** Parse a duration string to seconds (for peak-rate / Little's-Law math). */
export function durationToSeconds(d) {
  if (typeof d === 'number') return d;
  const m = /^(\d+(?:\.\d+)?)(ms|s|m|h)$/.exec(String(d).trim());
  if (!m) throw new Error(`unparseable duration: ${d}`);
  const n = parseFloat(m[1]);
  return { ms: n / 1000, s: n, m: n * 60, h: n * 3600 }[m[2]];
}

/** Render a numeric rate as a Gatling Double literal (always carries a decimal point). */
function num(n) {
  const v = Number(n);
  return Number.isInteger(v) ? `${v}.0` : String(v);
}

function isSteady(shape) {
  return shape == null || shape === 'steady' || shape === 'plateau' || shape === 'constant';
}

/**
 * Build the Gatling injection profile for the whole run (one scenario carries the
 * journey mix via randomSwitch, so the arrival profile is NOT weight-split here).
 *
 * Returns { steps:[scala strings], model, peakRate, maxConcurrent, warnings }.
 */
export function buildInjection(arrivalProfile, opts = {}) {
  const warnings = [];
  const stages = arrivalProfile.stages || [];
  if (stages.length === 0) throw new Error('arrivalProfile.stages is empty');
  const open = arrivalProfile.model !== 'closed';

  const peakRate = stages.reduce((mx, s) => Math.max(mx, Number(s.rate) || 0), 0);
  const ll = arrivalProfile.littlesLawCheck || {};
  // Little's Law ceiling: concurrency ~ arrival rate x mean service time. Prefer the
  // model's expectedConcurrency; else fall back to the peak rate as a floor.
  const maxConcurrent = Math.max(1, Math.ceil(ll.expectedConcurrency != null ? ll.expectedConcurrency : peakRate));

  const steps = [];
  let prev = 0; // previous stage end rate (open) / concurrency (closed)
  for (const s of stages) {
    const rate = Number(s.rate) || 0;
    const dur = scalaDuration(s.duration);
    const steady = isSteady(s.shape);
    if (open) {
      if (steady) steps.push(`constantUsersPerSec(${num(rate)}).during(${dur})`);
      else steps.push(`rampUsersPerSec(${num(prev)}).to(${num(rate)}).during(${dur})`);
      prev = rate;
    } else {
      const c = Math.max(0, Math.round(rate));
      if (steady) steps.push(`constantConcurrentUsers(${c}).during(${dur})`);
      else steps.push(`rampConcurrentUsers(${Math.round(prev)}).to(${c}).during(${dur})`);
      prev = c;
    }
  }

  // G3: a ramping profile that does not already cool down to zero gets one appended.
  const last = stages[stages.length - 1];
  const endsAtZero = (Number(last.rate) || 0) === 0;
  const anyRamp = stages.some((s) => !isSteady(s.shape));
  if (anyRamp && !endsAtZero) {
    const coolDur = scalaDuration(stages.find((s) => s.shape === 'ramp_up') ? stages.find((s) => s.shape === 'ramp_up').duration : last.duration);
    if (open) steps.push(`rampUsersPerSec(${num(Number(last.rate) || 0)}).to(0.0).during(${coolDur})`);
    else steps.push(`rampConcurrentUsers(${Math.round(Number(last.rate) || 0)}).to(0).during(${coolDur})`);
    warnings.push('ramp-down to 0 synthesized (arrival profile ended above zero)');
  }

  return { steps, model: open ? 'open' : 'closed', peakRate, maxConcurrent, warnings };
}
