// arrival.mjs — arrivalProfile -> k6 executor mapping (G3, §3.1 step 5, §3.3 rule 2).
//
// One k6 scenario per journey. Stage rates are scaled by the journey weight so
// the journey mix is reproduced by construction. A terminal ramp-down to zero is
// mandatory (§3.3 rule 2); if the approved model omits it, SYNTHESIZE appends one.

/** Parse a k6 duration string ('5m','30s','1h','500ms') to seconds. */
export function durationToSeconds(d) {
  if (typeof d === 'number') return d;
  const m = /^(\d+(?:\.\d+)?)(ms|s|m|h)$/.exec(String(d).trim());
  if (!m) throw new Error(`unparseable duration: ${d}`);
  const n = parseFloat(m[1]);
  switch (m[2]) {
    case 'ms':
      return n / 1000;
    case 's':
      return n;
    case 'm':
      return n * 60;
    case 'h':
      return n * 3600;
    default:
      throw new Error(`unparseable duration unit: ${d}`);
  }
}

function lastStageRampsToZero(stages) {
  const last = stages[stages.length - 1];
  return last && Number(last.rate) === 0;
}

/**
 * Ensure the stage list ends with a ramp-down to 0 (G3). Returns a possibly
 * extended copy plus a flag indicating whether a ramp-down was synthesized.
 */
export function enforceRampDown(stages) {
  if (stages.length === 0) throw new Error('arrivalProfile.stages is empty');
  if (lastStageRampsToZero(stages)) return { stages: stages.slice(), appended: false };
  // default cool-down = duration of the first ramp_up stage, else the first stage
  const rampUp = stages.find((s) => s.shape === 'ramp_up') || stages[0];
  const appended = { duration: rampUp.duration, rate: 0, shape: 'ramp_down' };
  return { stages: [...stages, appended], appended: true };
}

/**
 * Build the k6 scenario config for one journey.
 *   arrivalProfile — spec.arrivalProfile (model open|closed + stages)
 *   weight         — journey weight (rates scaled by this)
 *   opts           — { concurrency, caps, startTimeSec }
 * Returns { scenario, maxRate, maxVus, warnings }.
 */
export function buildScenario(journeyId, arrivalProfile, weight, opts = {}) {
  const warnings = [];
  const caps = opts.caps || {};
  // A single steady stage maps to a constant executor — no ramp-down applies.
  // Only ramping profiles must cool down to zero (G3, §3.3 rule 2).
  const steady =
    arrivalProfile.stages.length === 1 &&
    (arrivalProfile.stages[0].shape === 'steady' || arrivalProfile.stages[0].shape == null);
  let rawStages = arrivalProfile.stages.slice();
  if (!steady) {
    const r = enforceRampDown(arrivalProfile.stages);
    rawStages = r.stages;
    if (r.appended) warnings.push(`ramp-down stage synthesized for scenario "${journeyId}" (model ended above zero)`);
  }

  const scaled = rawStages.map((s) => ({
    target: round2(Number(s.rate) * weight),
    duration: s.duration,
    shape: s.shape,
  }));
  const peakRate = scaled.reduce((mx, s) => Math.max(mx, s.target), 0);

  // VU ceiling from Little's Law: concurrency ~ peakRate x mean service time.
  const concurrency = opts.concurrency != null ? opts.concurrency : Math.max(1, peakRate);
  let preAllocatedVUs = Math.max(5, Math.ceil(concurrency * 1.25));
  let maxVus = Math.ceil(preAllocatedVUs * 1.5);
  if (caps.maxVus != null && maxVus > caps.maxVus) {
    maxVus = caps.maxVus;
    if (preAllocatedVUs > maxVus) preAllocatedVUs = maxVus;
    warnings.push(`scenario "${journeyId}" VU ceiling clamped to caps.maxVus=${caps.maxVus}`);
  }

  const isOpen = arrivalProfile.model === 'open';

  let scenario;
  if (isOpen) {
    if (steady) {
      scenario = {
        executor: 'constant-arrival-rate',
        rate: scaled[0].target,
        timeUnit: '1s',
        duration: scaled[0].duration,
        preAllocatedVUs,
        maxVUs: maxVus,
      };
    } else {
      scenario = {
        executor: 'ramping-arrival-rate',
        startRate: 0,
        timeUnit: '1s',
        preAllocatedVUs,
        maxVUs: maxVus,
        stages: scaled.map((s) => ({ target: s.target, duration: s.duration })),
      };
    }
  } else if (steady) {
    scenario = {
      executor: 'constant-vus',
      vus: Math.max(1, Math.round(scaled[0].target)),
      duration: scaled[0].duration,
    };
  } else {
    scenario = {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: scaled.map((s) => ({ target: Math.max(0, Math.round(s.target)), duration: s.duration })),
    };
  }
  scenario.exec = journeyId;
  if (opts.startTimeSec) scenario.startTime = `${opts.startTimeSec}s`;
  scenario.tags = { journey: journeyId };

  return { scenario, maxRate: peakRate, maxVus, warnings };
}

function round2(n) {
  return Math.round(n * 100) / 100;
}
