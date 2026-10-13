"""ISI-5723 rev2 — FULL LIVE extraction driver for the PAC "load the program" demo.

Runs the Astroshop frontend DQL pack LIVE against the Dynatrace tenant (dtctl context
`tenant-b` = wkf10640, readonly) and emits a fresh `wkf10640_extract.live.json` in the
exact schema `build_wkf10640.py` already consumes. The deterministic build + renderers
(k6 / JMeter) then run unchanged on the live model — no pre-baked workload-model.json as
the source. This is the on-stage path; the committed 3h extract stays as the recorded
fallback.

What is LIVE (re-queried every run, the numbers the room will probe):
  - total frontend root traces            fetch spans | is_root_span & frontend | countDistinctApprox(trace.id)
  - order-terminal reach (buyer traces)   fetch spans | checkout||payment       | countDistinctApprox(trace.id)
  - frontend server baseline p50/95/99    fetch spans | server & frontend       | percentile/avg/count/countIf
  - server busy-integral -> concurrency   fetch spans | server & frontend       | sum(duration),count()
  - per-minute arrival curve (CoV)        ... | makeTimeseries count() interval:1m
  - product key cardinality + zipf counts fetch spans | product-catalog         | count() by app.product.id
  - R1 sampling ratio probe               fetch spans | frontend root           | avg(dt.system.sampling_ratio)

What is REUSED from the captured structural base (stable across the same otel-demo image;
the frontend journey *structure* does not change minute-to-minute — only its volumetrics):
  - buyer_steps / browser_steps trace-tree step lists + codeRefs
  - route surface identities, buyer funnel narration, product key identities
  - access-log availability (mesh ships none here), session-stitch note

The "glitch in the Matrix": `fetch user.events` is scope-gated (403, missing
`storage:user.events:read`, ISI-5719). We probe it live, catch the 403, and degrade
gracefully to spans + user.sessions — exactly as narrated on stage. Nothing in the model
depends on user.events (journeys are span-order reconstructed), so the degrade is lossless
for this demo and is recorded on the output for auditability.

Run:  python3 live_extract.py [--context tenant-b] [--window 3h] [--out <path>]
Exit 0 iff the live span pack succeeded (user.events 403 is expected, not a failure).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STRUCT_BASE = HERE.parent / "fixtures" / "wkf10640_extract.json"
DEFAULT_OUT = HERE.parent / "fixtures" / "wkf10640_extract.live.json"

NS_PER_MS = 1_000_000
FRONTEND = "frontend"


def _window_seconds(window: str) -> int:
    unit = window[-1]
    n = int(window[:-1])
    return n * {"h": 3600, "m": 60, "d": 86400, "s": 1}[unit]


def dql(context: str, query: str, *, allow_403: bool = False) -> dict:
    """Run one DQL query via dtctl and return the parsed result.

    Returns {"records": [...]} on success, or {"error_403": msg} when a 403 is
    tolerated (user.events). Raises on any other failure so a broken live pack
    surfaces loudly rather than silently poisoning the model.
    """
    proc = subprocess.run(
        ["dtctl", "query", "--context", context, "-o", "json", query],
        capture_output=True, text=True, timeout=120,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if out.startswith("{"):
        payload = json.loads(out)
        if "records" in payload:
            return payload
        msg = json.dumps(payload.get("error", payload))
        if allow_403 and "403" in msg:
            return {"error_403": msg}
        raise RuntimeError(f"DQL failed: {msg}")
    # dtctl may put the error envelope on stderr
    if allow_403 and "403" in (out + err):
        return {"error_403": (out + err)[:400]}
    raise RuntimeError(f"DQL produced no JSON records.\nstdout={out[:400]}\nstderr={err[:400]}")


def one(context: str, query: str, field: str, cast=float):
    rec = dql(context, query)["records"]
    return cast(rec[0][field]) if rec else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", default="tenant-b")
    ap.add_argument("--window", default="3h", help="DQL lookback, e.g. 3h / 90m / 24h")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    ctx, win = args.context, args.window
    wsec = _window_seconds(win)
    base = json.loads(STRUCT_BASE.read_text())
    fr = f'from:now()-{win}'

    def log(m): print(f"[live_extract] {m}", file=sys.stderr)

    log(f"context={ctx} window={win} ({wsec}s) -> {args.out}")

    # --- LIVE volumetrics ---------------------------------------------------
    total_root = one(ctx,
        f'fetch spans, {fr} | filter request.is_root_span==true and service.name=="{FRONTEND}" '
        f'| summarize c=countDistinctApprox(trace.id)', "c", int)
    log(f"total frontend root traces = {total_root:,}")

    buyer = one(ctx,
        f'fetch spans, {fr} | filter service.name=="checkout" or service.name=="payment" '
        f'| summarize c=countDistinctApprox(trace.id)', "c", int)
    # a buyer trace is a frontend root trace that reaches an order-terminal service;
    # clamp to total so the split stays well-formed under approx-count skew.
    buyer = min(buyer, total_root)
    browser = total_root - buyer
    log(f"order split: buyer={buyer:,}  browser={browser:,}")

    bl = dql(ctx,
        f'fetch spans, {fr} | filter span.kind=="server" and service.name=="{FRONTEND}" '
        f'| summarize p50=percentile(duration,50),p90=percentile(duration,90),'
        f'p95=percentile(duration,95),p99=percentile(duration,99),mean=avg(duration),'
        f'cnt=count(),errs=countIf(request.is_failed==true)')["records"][0]
    ms = lambda v: round(float(v) / NS_PER_MS, 3)
    server_baseline = {
        "p50_ms": ms(bl["p50"]), "p90_ms": ms(bl["p90"]), "p95_ms": ms(bl["p95"]),
        "p99_ms": ms(bl["p99"]), "mean_ms": ms(bl["mean"]),
        "count": int(bl["cnt"]), "errs": int(bl["errs"]),
    }
    log(f"server baseline frontend: p50={server_baseline['p50_ms']}ms "
        f"p99={server_baseline['p99_ms']}ms cnt={server_baseline['count']:,}")

    busy = dql(ctx,
        f'fetch spans, {fr} | filter span.kind=="server" and service.name=="{FRONTEND}" '
        f'| summarize sumdur=sum(duration),cnt=count()')["records"][0]
    busy_s = float(busy["sumdur"]) / 1e9          # ns -> s
    srv_cnt = int(busy["cnt"])
    server_rate_tps = round(srv_cnt / wsec, 2)
    observed_concurrency = round(busy_s / wsec, 4)  # Little's Law busy-integral / window
    log(f"server_rate_tps={server_rate_tps}  observed_concurrency={observed_concurrency}")

    ts = dql(ctx,
        f'fetch spans, {fr} | filter request.is_root_span==true and service.name=="{FRONTEND}" '
        f'| makeTimeseries c=count(), interval:1m')["records"][0]
    per_minute_counts = [int(x) if x is not None else 0 for x in ts["c"]]
    log(f"arrival curve: {len(per_minute_counts)} bins")

    pk = dql(ctx,
        f'fetch spans, {fr} | filter service.name=="product-catalog" and isNotNull(app.product.id) '
        f'| summarize reads=count(), by:{{app.product.id}} | sort reads desc')["records"]
    access_counts = {r["app.product.id"]: int(r["reads"]) for r in pk if r.get("app.product.id")}
    product_keys = {
        "distinct": len(access_counts),
        "reads": sum(access_counts.values()),
        "access_counts": access_counts or base["product_keys"]["access_counts"],
    }
    log(f"product keys: distinct={product_keys['distinct']} reads={product_keys['reads']:,}")

    # R1 sampling ratio (defaults to 1.0 if the attribute is absent on this tenant)
    try:
        sr = one(ctx,
            f'fetch spans, {fr} | filter request.is_root_span==true and service.name=="{FRONTEND}" '
            f'| summarize s=avg(dt.system.sampling_ratio)', "s", float)
        sampling_ratio = round(sr, 4) if sr else 1.0
    except Exception:
        sampling_ratio = 1.0
    log(f"sampling_ratio={sampling_ratio}")

    # --- the "glitch in the Matrix": user.events is scope-gated (ISI-5719) ---
    ue = dql(ctx, f'fetch user.events, {fr} | summarize c=count()', allow_403=True)
    user_events_degraded = "error_403" in ue
    log("user.events: 403 scope-gated -> graceful degrade to spans + user.sessions"
        if user_events_degraded else f"user.events: AVAILABLE ({ue['records']})")

    # user.sessions is reachable (dual-source stitch denominator / coverage narration)
    try:
        sess = one(ctx, f'fetch user.sessions, {fr} | summarize c=count()', "c", int)
    except Exception:
        sess = None
    log(f"user.sessions count = {sess}")

    # --- assemble the live fixture (live volumetrics + structural base) -----
    buyer_svc = next((j["svc_set"] for j in base["journeys"] if "buyer" in j["op"]), [])
    browser_svc = next((j["svc_set"] for j in base["journeys"] if "browser" in j["op"]), [])

    live = dict(base)  # inherit structural fields (buyer_steps, browser_steps, route surface, funnel)
    live["_comment"] = (
        "LIVE extraction (ISI-5723 rev2): volumetrics re-queried live via dtctl context "
        f"'{args.context}' (wkf10640) over a {win} window; journey STRUCTURE (step trees, "
        "codeRefs, route identities, buyer funnel) reused from the captured structural base "
        "(stable across the same otel-demo image). Nothing depends on user.events."
    )
    live["environment"] = base["environment"]
    live["timeframe"] = f"-{win} (LIVE, demo run)"
    live["window_seconds"] = wsec
    live["sampling_ratio"] = sampling_ratio
    live["journeys"] = [
        {"op": "buyer_checkout_flow", "traces": buyer, "svc_set": buyer_svc},
        {"op": "browser_browse_flow", "traces": browser, "svc_set": browser_svc},
    ]
    live["per_minute_counts"] = per_minute_counts
    live["server_baseline_frontend"] = server_baseline
    live["server_rate_tps"] = server_rate_tps
    live["observed_concurrency"] = observed_concurrency
    live["product_keys"] = product_keys
    live["order_split"] = {
        "buyer_traces": buyer, "browser_traces": browser,
        "buyer_share": round(buyer / total_root, 4) if total_root else 0.0,
        "browser_share": round(browser / total_root, 4) if total_root else 0.0,
        "signal": base["order_split"]["signal"].split("; total")[0]
                  + f"; total frontend root traces = {total_root}",
    }
    live["live_extraction"] = {
        "ran_at_window": win,
        "total_root_traces": total_root,
        "user_sessions_count": sess,
        "user_events_available": not user_events_degraded,
        "user_events_degrade_note": (
            "fetch user.events -> 403 NOT_AUTHORIZED_FOR_TABLE (missing storage:user.events:read, "
            "ISI-5719). Degraded to spans + user.sessions. Model journeys are span-order "
            "reconstructed, so the degrade is lossless for this demo."
        ) if user_events_degraded else None,
    }

    Path(args.out).write_text(json.dumps(live, indent=2) + "\n")
    log(f"wrote {args.out}")
    print(json.dumps({
        "out": args.out,
        "total_root_traces": total_root,
        "buyer_share": live["order_split"]["buyer_share"],
        "browser_share": live["order_split"]["browser_share"],
        "server_rate_tps": server_rate_tps,
        "observed_concurrency": observed_concurrency,
        "arrival_bins": len(per_minute_counts),
        "product_keys": product_keys["distinct"],
        "sampling_ratio": sampling_ratio,
        "user_events_degraded": user_events_degraded,
        "user_sessions_count": sess,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
