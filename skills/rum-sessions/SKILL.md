---
name: rum-sessions
description: >-
  RUM session-signal skill (SCOPE step 2c, preferred when RUM is present). Analyzes real-user
  session populations from Dynatrace Grail `user.sessions` — session shape (actions,
  navigations, duration, bounce, errors) per RUM app, plus per-app coverage — and feeds the
  measured session boundaries/lengths into workload modeling. Use when the user says "analyze
  RUM sessions", "real user session shape", or when scoping a browser-app workload model and
  RUM data exists.
---

# rum-sessions (RUM user-session signal)

Real-user session populations are the ground truth for session boundaries, session length,
and pacing in browser workloads. On Dynatrace they are **Grail/DQL-native** — no classic
USQL token needed:

- **`user.sessions`** — one row per real-user session: action/navigation counts, duration,
  bounce, errors, app. Usually readable with a plain read token.
- **`user.events`** — the per-session **ordered** navigation (views, actions, requests):
  exact sequences and per-action think-times. Needs OAuth scope `storage:user.events:read`.

## Tool

`utilities/rum_sessions.py` (mirror: `skills/workload-model/scripts/rum_sessions.py`) —
pure functions + CLI; you run the DQL, it analyzes the rows:

```bash
# 1. run against your tenant (any DQL client):
#    fetch user.sessions, from: -24h
#    | fields frontend.name, user_action_count, navigation_count,
#            duration, characteristics.is_bounce, error.count
# 2. analyze:
python3 utilities/rum_sessions.py shape < rows.json

# per-app coverage (attach to workload-model metadata.source.rumSessionCoverage):
python3 utilities/rum_sessions.py cover < per_app_rows.json
```

Configuration: `DT_ENDPOINT` / `DT_API_TOKEN` (see root `.env.example`) for whichever DQL
client you use. **Scrub PII** (geo / user / IP) from any RUM field before it reaches a
committed dataset.

## How the output is used

- `actionsPerSession` / `durationSeconds` distributions → journey think-time and session
  length parameters in the workload model.
- `meanInteractionGapSeconds` is an **estimate** (duration / (actions-1)); exact per-action
  think-times require `user.events` or the session-stitch path.
- Combined with spans via the dual-source merge (`skills/workload-model` step 2c): RUM
  session shape calibrates the unsampled span side; rum-only endpoints are dropped (nothing
  to drive server-side).

## Validity gates

- One row per **session**, not per action — check `user_action_count` distributions for
  sanity before trusting pacing.
- A RUM app with sessions but **no matching server spans** is frontend-only traffic; record
  it in coverage rather than modeling a server journey for it.
