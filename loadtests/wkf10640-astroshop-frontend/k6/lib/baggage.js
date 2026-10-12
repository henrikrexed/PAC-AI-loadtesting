// baggage.js — synthetic-traffic identity + OTel span emission (methodology P4, §3.3 rule 6, §7.7).
//
// Pure, dependency-free JS (no k6 globals) so it is unit-testable in Node and
// importable from generated k6 scripts. Every generated request routes its
// params through `syntheticParams()`, which guarantees:
//   1. the W3C `baggage: synthetic=true` header on the wire — the SDK/collector
//      baggage span processor (§7.7) promotes it to the queryable span attribute
//      `synthetic` that ANALYZE (§3.5) and the G5 smoke (crit 5) filter on;
//   2. a k6 metric tag `synthetic: "true"` for client-side separation.
//
// Span emission itself is produced by k6's tracing instrumentation
// (`instrumentHTTP` from 'k6/experimental/tracing'), enabled once at module
// scope in the generated script. Because baggage rides the propagated context,
// the emitted spans carry synthetic=true once promotion (§7.7) is in place.

export const SYNTHETIC_BAGGAGE = 'synthetic=true';

/**
 * Build k6 request params with the synthetic baggage header + tag always set.
 * Extra headers (e.g. a correlated auth token, Content-Type) are merged in;
 * an explicit `baggage` in extraHeaders is still forced to carry synthetic=true.
 */
export function syntheticParams(extraHeaders = {}, extraTags = {}) {
  const headers = { ...extraHeaders };
  headers.baggage = mergeBaggage(headers.baggage);
  return {
    headers,
    tags: { synthetic: 'true', ...extraTags },
  };
}

/**
 * Merge synthetic=true into an existing baggage header value without dropping
 * any caller-supplied baggage entries, and without duplicating the key.
 */
export function mergeBaggage(existing) {
  if (!existing || typeof existing !== 'string') return SYNTHETIC_BAGGAGE;
  const entries = existing
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !/^synthetic\s*=/.test(s));
  entries.push(SYNTHETIC_BAGGAGE);
  return entries.join(',');
}

/**
 * True iff a baggage header value carries synthetic=true. Used by V2a and tests
 * to assert the identity header is present on every request.
 */
export function carriesSynthetic(baggageValue) {
  if (typeof baggageValue !== 'string') return false;
  return baggageValue
    .split(',')
    .map((s) => s.trim())
    .some((s) => /^synthetic\s*=\s*true$/.test(s));
}
