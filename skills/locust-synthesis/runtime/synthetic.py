# synthetic.py — synthetic-traffic identity + OTel baggage (methodology P4, §3.3 rule 6, §7.7).
#
# Pure, dependency-free Python (no locust globals) so it is unit-testable and
# importable from the generated locustfile. Every generated request routes its
# headers through `synthetic_headers()`, which guarantees the W3C
# `baggage: synthetic=true` header on the wire — the OTel SDK / collector baggage
# span processor (§7.7) promotes it to the queryable span attribute `synthetic`
# that ANALYZE (§3.5) and the G5 smoke (crit 5) filter on. This is the Locust
# equivalent of the k6 `syntheticParams()` helper — same identity, same header.

SYNTHETIC_BAGGAGE = "synthetic=true"


def merge_baggage(existing):
    """Merge synthetic=true into an existing baggage header value without dropping
    any caller-supplied entries and without duplicating the key."""
    if not existing or not isinstance(existing, str):
        return SYNTHETIC_BAGGAGE
    entries = [
        e.strip()
        for e in existing.split(",")
        if e.strip() and not e.strip().lower().startswith("synthetic=")
    ]
    entries.append(SYNTHETIC_BAGGAGE)
    return ",".join(entries)


def synthetic_headers(extra=None):
    """Build a request headers dict with the synthetic baggage header always set.
    Extra headers (a correlated auth token/cookie, Content-Type) are merged in; an
    explicit `baggage` in `extra` is still forced to carry synthetic=true."""
    headers = dict(extra or {})
    headers["baggage"] = merge_baggage(headers.get("baggage"))
    return headers


def carries_synthetic(value):
    """True iff a baggage header value carries synthetic=true. Used by the static
    check and tests to assert the identity header is present on every request."""
    if not isinstance(value, str):
        return False
    return any(
        e.strip().lower().replace(" ", "") == "synthetic=true"
        for e in value.split(",")
    )


def instrument_otel():
    """Best-effort OTel client-span emission + baggage propagation.

    Enabled only when the OTel SDK is installed AND OTEL_EXPORTER_OTLP_ENDPOINT is
    set; a no-op otherwise, so headless/CI runs and `py_compile` never require the
    opentelemetry packages (see runtime/requirements.txt). This is the Locust
    counterpart to k6's `instrumentHTTP()`: the emitted client spans ride the
    propagated context, so once baggage->attribute promotion (§7.7) is in place
    they carry synthetic=true. Returns True iff instrumentation was activated."""
    import os

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        return True
    except Exception:
        return False
