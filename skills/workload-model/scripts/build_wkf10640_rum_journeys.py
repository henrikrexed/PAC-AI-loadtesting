"""ISI-5719 — assemble RUM-primary ordered-journey models from live `user.events` (wkf10640).

Scope `storage:user.events:read` granted on the wkf10640 dt0s16 token (board, 2026-10-13), so
the drop-in `rum_events.py` stitcher runs on real data. **App-agnostic by design** — the same
pipeline runs for any RUM app in the tenant; this script ships two: `Astroshop` (otel-demo
e-commerce) and `EasyTrade` (a wholly different trading app), to prove it's not app-specific.

Pipeline per app (data pulled by the caller via dtctl context `tenant-b-events`, DQL headers in
each `/tmp/*.json`):
  <journeys>  per-session ordered view arrays (view.name, canonicalised in DQL)  -> journey templates
  <think>     per-page view_summary duration pctls                               -> measured think-times
  <rum_ep>    per-endpoint RUM request counts (raw url.path)   -> Python-canonicalised, static-asset
  <span_ep>   per-endpoint server-span counts (raw url.path)   -> filtered, then source_merge.merge_plan

Endpoint canonicalisation is shared & deterministic (templating numeric/uuid/hex id segments,
dropping browser static assets) so RUM browser paths and server-span paths join where they match;
the rest fall to span-only (internal/proxy-rewritten) exactly as the board's merge rules intend.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import source_merge  # noqa: E402

WINDOW_S = 86400.0
OUT = Path("loadtests/wkf10640-astroshop-frontend")

# --- shared endpoint canonicalisation -------------------------------------------------------
_STATIC = re.compile(
    r"(\.(js|css|svg|ico|png|jpe?g|gif|woff2?|map)$)|ruxitagentjs|/_next/|/assets/|favicon", re.I)
_SEG_NUM = re.compile(r"/\d+(?=/|$)")
_SEG_UUID = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{20,}(?=/|$)")
_SEG_HEX = re.compile(r"/[0-9A-Z]{8,}(?=/|$)")           # astroshop product slugs e.g. HQTGWGPNH4
_IMG = re.compile(r"/api/images/[^/]+$")


def is_static(path: str) -> bool:
    return bool(_STATIC.search(path)) or path in ("", "/")


def canon_endpoint(path: str) -> str:
    p = _IMG.sub("/api/images/:file:", path)
    p = _SEG_UUID.sub("/:uuid:", p)
    p = _SEG_NUM.sub("/:id:", p)
    p = _SEG_HEX.sub("/:id:", p)
    return p


def endpoint_rates(path_counts_file: str) -> dict[str, float]:
    """Raw {path,c} rows -> canonical endpoint -> req/s, dropping browser static assets."""
    agg: collections.Counter = collections.Counter()
    for r in json.loads(Path(f"/tmp/{path_counts_file}").read_text())["records"]:
        path = r.get("path") or ""
        if is_static(path):
            continue
        agg[canon_endpoint(path)] += int(r["c"])
    return {k: round(v / WINDOW_S, 6) for k, v in agg.items()}


# --- per-app assembly -----------------------------------------------------------------------

def journey_templates(journeys_file: str):
    recs = json.loads(Path(f"/tmp/{journeys_file}").read_text())["records"]
    total = len(recs)
    seqs: collections.Counter = collections.Counter()
    for r in recs:
        seqs[" > ".join(r.get("views") or [])] += 1
    out = [{
        "sequence": j.split(" > ") if j else [],
        "sessions": n,
        "weight": round(n / total, 4),
        "steps": len(j.split(" > ")) if j else 0,
    } for j, n in seqs.most_common()]
    return out, total


def think_times(think_file: str) -> dict:
    out = {}
    for r in json.loads(Path(f"/tmp/{think_file}").read_text())["records"]:
        out[r["page"]] = {
            "n": int(r["n"]),
            "p50Ms": round(float(r["p50"]) / 1e6, 1),
            "p90Ms": round(float(r["p90"]) / 1e6, 1),
            "p99Ms": round(float(r["p99"]) / 1e6, 1),
            "meanMs": round(float(r["mn"]) / 1e6, 1),
            "maxMs": round(float(r["mx"]) / 1e6, 1),
        }
    return out


APPS = [
    {"key": "astroshop", "app": "Astroshop", "sessions": 18773, "spanNs": "astroshop",
     "journeys": "journeys.json", "think": "think.json",
     "rum_ep": "as_rum_ep.json", "span_ep": "as_span_ep.json",
     "note": "otel-demo e-commerce"},
    {"key": "easytrade", "app": "EasyTrade", "sessions": 15351, "spanNs": "easytrade",
     "journeys": "et_journeys.json", "think": "et_think.json",
     "rum_ep": "et_rum_ep.json", "span_ep": "et_span_ep.json",
     "note": "trading app — a wholly different app from Astroshop"},
]


def build(app: dict) -> dict:
    templates, total = journey_templates(app["journeys"])
    think = think_times(app["think"])
    rum_rates = endpoint_rates(app["rum_ep"])
    span_rates = endpoint_rates(app["span_ep"])
    merge = source_merge.merge_plan(rum_rates, span_rates)
    model = {
        "source": {"tenant": "wkf10640", "app": app["app"], "object": "user.events",
                   "windowHours": 24, "sessions": app["sessions"], "spanNamespace": app["spanNs"],
                   "scope": "storage:user.events:read (granted 2026-10-13)", "note": app["note"]},
        "journeyTemplates": templates,
        "thinkTimeByPage": think,
        "perEndpointMerge": merge,
    }
    (OUT / f"rum-journey-model-{app['key']}.json").write_text(json.dumps(model, indent=2))
    return model


def md_section(model: dict) -> list[str]:
    s = model["source"]
    L = [f"# wkf10640 / {s['app']} — RUM-primary ordered journeys (ISI-5719)", "",
         f"_{s['note']}._ Live `user.events`, 24h, **{s['sessions']:,} sessions**.", "",
         f"## Ordered journey templates ({len(model['journeyTemplates'])} distinct, top 8)", "",
         "| sessions | weight | steps | sequence |", "|---:|---:|---:|---|"]
    for t in model["journeyTemplates"][:8]:
        L.append(f"| {t['sessions']:,} | {t['weight']*100:.1f}% | {t['steps']} | "
                 f"`{' > '.join(t['sequence'])}` |")
    L += ["", "## Measured per-page think-time (view dwell, ms)", "",
          "| page | n | p50 | p90 | mean |", "|---|---:|---:|---:|---:|"]
    for page, d in model["thinkTimeByPage"].items():
        L.append(f"| `{page}` | {d['n']:,} | {d['p50Ms']:.0f} | {d['p90Ms']:.0f} | {d['meanMs']:.0f} |")
    m = model["perEndpointMerge"]; su = m["summary"]
    L += ["", "## Per-endpoint overlap & extrapolation (RUM ⟗ spans)", "",
          "| endpoint | source | RUM req/s | span req/s | factor |", "|---|---|---:|---:|---:|"]
    for e in m["entries"][:12]:
        rr = f"{e['rumRate']:.3f}" if e["rumRate"] is not None else "—"
        sr = f"{e['spanRate']:.3f}" if e["spanRate"] is not None else "—"
        fa = f"{e['extrapolationFactor']:.2f}" if e["extrapolationFactor"] is not None else "—"
        L.append(f"| `{e['key']}` | {e['source']} | {rr} | {sr} | {fa} |")
    L += ["", f"**Summary:** {su['keys']} endpoints · {su['rumPrimaryKeys']} RUM-primary · "
          f"{su['spanFallbackKeys']} span-only · rumDrivenShare {su['rumDrivenShare']} · "
          f"mean extrapolation ×{su['meanExtrapolationFactor']}.", ""]
    return L


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = []
    for app in APPS:
        model = build(app)
        md += md_section(model) + ["---", ""]
        su = model["perEndpointMerge"]["summary"]
        print(f"{app['app']}: {len(model['journeyTemplates'])} templates, "
              f"{len(model['thinkTimeByPage'])} pages, {su['keys']} endpoints "
              f"({su['rumPrimaryKeys']} rum-primary), rumDrivenShare {su['rumDrivenShare']}")
    (OUT / "rum-journey-sidebyside.md").write_text("\n".join(md))
    print("wrote per-app models + rum-journey-sidebyside.md")


if __name__ == "__main__":
    main()
