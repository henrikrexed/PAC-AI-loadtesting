---
name: session-stitch
description: >-
  Session reconstruction from OTel `session.id` on spans (SCOPE step 2c tier ii). Groups
  spans by session.id, orders them, and derives REAL per-session action sequences, measured
  inter-action think-times, and session boundaries — closing the "no notion of a session" gap
  without any RUM dependency. Use when the user says "stitch sessions", "session think-times
  from spans", or when spans carry session.id and the workload model needs measured pacing.
---

# session-stitch (OTel session.id reconstruction)

Where spans carry an OTel `session.id` (the OTel *session* semantic convention, propagated
as baggage → attribute), this skill reconstructs **real session chains**:

- groups spans by `session.id`,
- orders them by start time → the real per-session action sequence,
- diffs consecutive actions → **genuine inter-action think-times**, and
- derives session boundaries / length,

feeding the workload model's sequence reconstructor with measured sessions instead of
span-order inference. Works for **any** service that propagates `session.id` — browser
front-ends *and* non-browser apps (agents, gRPC services).

## Tool

`utilities/session_stitch.py` (mirror: `skills/workload-model/scripts/session_stitch.py`) —
pure functions + CLI; you run the DQL, it stitches the rows:

```bash
# 1. run against your tenant:
#    fetch spans, from: -24h
#    | filter isNotNull(session.id)
#    | fields session.id, start_time, duration, service.name, span.name
# 2. stitch:
python3 utilities/session_stitch.py stitch < rows.json
python3 utilities/session_stitch.py stitch < rows.json --max-gap-s 1800   # split long-lived ids

# coverage report (attach to workload-model metadata.source.sessionIdCoverage):
python3 utilities/session_stitch.py cover < coverage_rows.json
```

## Validity check (run BEFORE using output for pacing)

The id must sit on each **action's entry span**. A leaf-/single-op id (e.g. an ad-fetch
call) yields only that op's *cadence*, not a journey. Verify via
`session.id → trace.id → entry-op` and a funnel-reach join before using it for pacing.
Where `session.id` is absent, the span-order method is the fallback and the model records
**0% session.id coverage** alongside the span sampling ratio so fidelity stays auditable.

## Output

- `sessionLength` — actions-per-session and session-duration distributions.
- `thinkTime` — measured inter-action think-time distribution (ms).
- `thinkTimeSpec` — a schema-valid `thinkTime` object (`empirical` samples or `exponential`
  mean) to attach to a journey step; `null` when there is no think-time signal
  (single-action sessions) so no think-time is fabricated.
