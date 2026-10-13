// think.js — per-step think-time sampling (pure JS; used by generated k6 scripts + tests).
// `rand` in [0,1) is supplied by the caller (Math.random() in k6).

export function thinkSeconds(spec, rand) {
  if (!spec || !spec.distribution) return 0;
  switch (spec.distribution) {
    case 'constant':
      return (spec.meanMs ?? 0) / 1000;
    case 'uniform': {
      const lo = spec.minMs ?? 0;
      const hi = spec.maxMs ?? lo;
      return (lo + rand * (hi - lo)) / 1000;
    }
    case 'exponential': {
      const mean = spec.meanMs ?? 0;
      // inverse-CDF of exponential; guard rand=0 -> log(1)
      return (-Math.log(1 - Math.min(rand, 0.999999)) * mean) / 1000;
    }
    case 'empirical': {
      const s = spec.samples || [];
      if (s.length === 0) return 0;
      return s[Math.min(s.length - 1, Math.floor(rand * s.length))] / 1000;
    }
    default:
      return 0;
  }
}
