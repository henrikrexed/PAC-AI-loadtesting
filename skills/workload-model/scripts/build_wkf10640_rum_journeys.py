"""ISI-5719 — assemble the RUM-primary ordered-journey model for wkf10640 / Astroshop.

Consumes the live `user.events` extraction (board granted `storage:user.events:read` on the
wkf10640 dt0s16 token, 2026-10-13) and the span side, producing the merged model + a side-by-side
report. Reads the raw DQL JSON pulled by the caller (dtctl, context `tenant-b-events`) from
`/tmp/*.json` — see the header of each file for the exact query — and emits deterministic artifacts.

Pipeline:
  journeys.json  (per-session ordered view arrays)  -> ordered journey templates (weighted)
  think.json     (per-page view_summary duration pctls) -> per-step measured think-times
  rum_ep.json    (per-endpoint RUM request req/s)    -> RUM-primary endpoint rates
  span_ep.json   (per-endpoint server-span req/s)    -> span truth
                 reconciled via source_merge.merge_plan -> per-endpoint overlap + extrapolation

Modeling note (real-data finding): in this RUM dataset `user_action` events are labelled by
their *page* (no distinct action name), so the clean use-case sequence is the ordered
`view_summary` views; `rum_events.journey_templates` over views-only is the authoritative
sequence (including actions double-counts the page). Think-time per step = the view's dwell
(`view_summary.duration`), which is exactly the inter-action pacing the model needs.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import source_merge  # noqa: E402

WINDOW_S = 86400.0          # 24h extraction window
SESSIONS = 18773            # distinct Astroshop sessions in window (countDistinctExact)
OUT = Path("loadtests/wkf10640-astroshop-frontend")


def _load(name: str) -> list[dict]:
    return json.loads(Path(f"/tmp/{name}").read_text())["records"]


def journey_templates() -> list[dict]:
    seqs: collections.Counter = collections.Counter()
    recs = _load("journeys.json")
    total = len(recs)
    for r in recs:
        seqs[" > ".join(r.get("views") or [])] += 1
    out = []
    for journey, n in seqs.most_common():
        out.append({
            "sequence": journey.split(" > ") if journey else [],
            "sessions": n,
            "weight": round(n / total, 4),
            "steps": len(journey.split(" > ")) if journey else 0,
        })
    return out, total


def think_times() -> dict:
    out = {}
    for r in _load("think.json"):
        out[r["page"]] = {
            "n": int(r["n"]),
            "p50Ms": round(float(r["p50"]) / 1e6, 1),
            "p90Ms": round(float(r["p90"]) / 1e6, 1),
            "p99Ms": round(float(r["p99"]) / 1e6, 1),
            "meanMs": round(float(r["mn"]) / 1e6, 1),
            "maxMs": round(float(r["mx"]) / 1e6, 1),
        }
    return out


def endpoint_rates(name: str, api_only: bool = True) -> dict[str, float]:
    rates = {}
    for r in _load(name):
        ep = r["ep"]
        if api_only and not ep.startswith("/api/"):
            continue
        rates[ep] = round(int(r["c"]) / WINDOW_S, 6)
    return rates


def main() -> None:
    templates, total = journey_templates()
    think = think_times()
    rum_rates = endpoint_rates("rum_ep.json")
    span_rates = endpoint_rates("span_ep.json")
    merge = source_merge.merge_plan(rum_rates, span_rates)

    model = {
        "source": {
            "tenant": "wkf10640",
            "app": "Astroshop",
            "object": "user.events",
            "windowHours": 24,
            "sessions": SESSIONS,
            "scope": "storage:user.events:read (granted 2026-10-13)",
            "rumSpanJoinKey": "trace.id / span.id present on request events",
        },
        "journeyTemplates": templates,
        "thinkTimeByPage": think,
        "perEndpointMerge": merge,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rum-journey-model.json").write_text(json.dumps(model, indent=2))

    # ---- markdown side-by-side ----
    L = []
    L.append("# wkf10640 / Astroshop — RUM-primary ordered journeys (ISI-5719)")
    L.append("")
    L.append(f"Live `user.events` extraction, 24h, **{SESSIONS:,} sessions**. Scope "
             "`storage:user.events:read` granted 2026-10-13 (board token).")
    L.append("")
    L.append(f"## Ordered journey templates ({len(templates)} distinct, top 10)")
    L.append("")
    L.append("| sessions | weight | steps | sequence |")
    L.append("|---:|---:|---:|---|")
    for t in templates[:10]:
        L.append(f"| {t['sessions']:,} | {t['weight']*100:.1f}% | {t['steps']} | "
                 f"`{' > '.join(t['sequence'])}` |")
    L.append("")
    L.append("## Measured per-page think-time (view dwell, ms)")
    L.append("")
    L.append("| page | n | p50 | p90 | p99 | mean |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for page, d in think.items():
        L.append(f"| `{page}` | {d['n']:,} | {d['p50Ms']:.0f} | {d['p90Ms']:.0f} | "
                 f"{d['p99Ms']:.0f} | {d['meanMs']:.0f} |")
    L.append("")
    L.append("## Per-endpoint overlap & extrapolation (RUM ⟗ spans, `/api/*`)")
    L.append("")
    L.append("| endpoint | source | RUM req/s | span req/s | factor |")
    L.append("|---|---|---:|---:|---:|")
    for e in merge["entries"]:
        rr = f"{e['rumRate']:.3f}" if e["rumRate"] is not None else "—"
        sr = f"{e['spanRate']:.3f}" if e["spanRate"] is not None else "—"
        fa = f"{e['extrapolationFactor']:.2f}" if e["extrapolationFactor"] is not None else "—"
        L.append(f"| `{e['key']}` | {e['source']} | {rr} | {sr} | {fa} |")
    s = merge["summary"]
    L.append("")
    L.append(f"**Summary:** {s['keys']} endpoints · {s['rumPrimaryKeys']} RUM-primary · "
             f"{s['spanFallbackKeys']} span-only · rumDrivenShare {s['rumDrivenShare']} · "
             f"mean extrapolation ×{s['meanExtrapolationFactor']} "
             f"(range {s['extrapolationFactorRange']}).")
    (OUT / "rum-journey-sidebyside.md").write_text("\n".join(L) + "\n")

    print("journey templates:", len(templates), "| think pages:", len(think),
          "| endpoints merged:", s["keys"], "rum-primary", s["rumPrimaryKeys"])
    print("wrote", OUT / "rum-journey-model.json", "and", OUT / "rum-journey-sidebyside.md")


if __name__ == "__main__":
    main()
