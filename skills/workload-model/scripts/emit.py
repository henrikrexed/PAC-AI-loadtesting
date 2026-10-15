"""Assemble workload-model.json and render scenario-proposal.md (methodology §4, §5.2).

`build_model` assembles a schema-shaped dict from the extracted facts (scenarios, arrival
stages, Little's Law check, per-scenario baselines, payloads). `render_proposal` renders
the §5.2 template, including the mandatory §11 residual caveats (R1 sampling, R2 mean!=peak,
R5 instrumentation coverage) so they are never silently dropped. `canonical_hash` stamps
status.hash with a sha256 over the canonicalized spec.

No telemetry I/O here — the caller runs the DQL pack and passes the numbers in.

Provenance (ISI-5928): every model carries `metadata.source.provenance` — either
`extracted` (with `extractedFrom: "<query pack> on tenant <Y> (<window>)"`) or
`demo-sample`. A model with no provenance fails G0 (fail-closed): there is no
"unknown-but-shipped" kind. Demo models render with an unmissable banner and are
refused by downstream consumers unless they explicitly opt in.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def canonical_hash(spec: dict[str, Any]) -> str:
    blob = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def make_extracted_provenance(
    query_pack: list[str], tenant: str, window: str, *, ran_at_iso: str | None = None
) -> dict[str, Any]:
    """Provenance for a model built from a live backend extraction."""
    ran = ran_at_iso or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "kind": "extracted",
        "extractedFrom": f"the SKILL.md DQL query pack ({len(query_pack)} queries) on tenant "
                         f"{tenant} ({window})",
        "queryPack": query_pack,
        "tenant": tenant,
        "window": window,
        "ranAtIso": ran,
        "dqlRunLive": True,
    }


def make_demo_provenance(note: str) -> dict[str, Any]:
    """Provenance for the demo/synthetic path — explicit opt-in only."""
    return {"kind": "demo-sample", "note": note}


def build_model(
    *,
    name: str,
    target_service: str,
    environment: str,
    generated_at: str,
    timeframe: str,
    timeframe_notes: str,
    queries: list[str],
    access_log_availability: str,
    sampling_ratio: float,
    arrival_model: str,
    stages: list[dict[str, Any]],
    littles_law: dict[str, float],
    journeys: list[dict[str, Any]],
    payloads: dict[str, Any],
    caps: dict[str, Any],
    coverage: float,
    session_id_coverage: dict[str, Any] | None = None,
    revision: int = 1,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = sorted({j.get("evidenceSource", "span") for j in journeys})
    spec = {
        "arrivalProfile": {
            "model": arrival_model,
            "stages": stages,
            "littlesLawCheck": littles_law,
        },
        "journeys": journeys,
        "payloads": payloads,
        "caps": caps,
        "coverage": round(coverage, 4),
    }
    model = {
        "apiVersion": "loadtest.isi/v1alpha1",
        "kind": "WorkloadModel",
        "metadata": {
            "name": name,
            "targetService": target_service,
            "environment": environment,
            "generatedAt": generated_at,
            "source": {
                "tool": "dtctl",
                "timeframe": timeframe,
                "timeframeNotes": timeframe_notes,
                "queries": queries,
                "evidenceSources": evidence,
                "accessLogAvailability": access_log_availability,
                "samplingRatio": sampling_ratio,
                **({"sessionIdCoverage": session_id_coverage} if session_id_coverage is not None else {}),
                "provenance": provenance if provenance is not None else {
                    "kind": "unknown",
                    "note": "no provenance recorded by the caller — G0 fails closed (ISI-5928); "
                            "rerun the engine with a real extract (adapter records provenance) "
                            "or pass --demo for the synthetic example",
                },
            },
        },
        "spec": spec,
        "status": {"revision": revision, "hash": canonical_hash(spec)},
    }
    return model


def render_proposal(
    model: dict[str, Any],
    *,
    exclusions: str,
    target_env: str,
    abort_note: str,
    risks_extra: list[str] | None = None,
) -> str:
    meta = model["metadata"]
    spec = model["spec"]
    src = meta["source"]
    name = meta["name"]
    rev = model["status"]["revision"]
    llc = spec["arrivalProfile"]["littlesLawCheck"]

    rows = []
    for j in spec["journeys"]:
        b = j["baseline"]
        rows.append(
            f"| `{j['id']}` | {j['weight']:.3f} | `{j['entrypoint']}` | "
            f"`{j.get('codeRef', '—')}` | {b['p95Ms']:.0f} | {j.get('evidenceSource', 'span')} |"
        )
    journey_table = "\n".join(rows)

    stage_rows = "\n".join(
        f"| {s['duration']} | {s['rate']} | {s.get('shape', '—')} |"
        for s in spec["arrivalProfile"]["stages"]
    )

    payload_lines = []
    for pid, pool in spec.get("payloads", {}).items():
        cp = pool.get("cacheProfile")
        cp_note = ""
        if cp:
            cp_note = (f" · cacheProfile: targetHitRatio={cp.get('targetHitRatio')}, "
                       f"keyCardinality={cp.get('keyCardinality')}, "
                       f"alpha={cp.get('distributionAlpha', 'uniform')}")
        payload_lines.append(f"- `{pid}` ({len(pool.get('fields', []))} field(s)){cp_note}")
    payload_block = "\n".join(payload_lines) or "- (none)"

    # Cache-reuse PII note only applies when a payload actually carries a cacheProfile
    # (commerce catalogs); omit it for workloads with no cache-fronted payload (e.g. agent apps).
    has_cache = any(p.get("cacheProfile") for p in spec.get("payloads", {}).values())
    cache_pii = (
        " Cache-fronted payload keys reuse the real telemetry-derived key set so the production "
        "cache hit ratio is reproduced rather than collapsed."
        if has_cache else ""
    )

    access = src.get("accessLogAvailability")
    access_caveat = (
        "**Access logs unavailable — spans-only extraction.** No Istio/Envoy `istio-proxy` "
        "log records were present on this tenant (probe returned 0 lines); the HTTP surface "
        "was recovered from server-span `span.name` routes instead of the mesh access log. "
        "The `istio-ingressgateway` cross-check (§3.1 step 2b) is therefore N/A; the front-end "
        f"was resolved from the span graph (entry server span `{meta['targetService']}`) and "
        "reach-confirmed. Un-instrumented hops that only an access log would reveal are not captured."
        if access == "unavailable"
        else f"Access-log availability: **{access}**."
    )

    prov = src.get("provenance") or {}
    prov_kind = prov.get("kind")
    if prov_kind == "extracted":
        provenance_line = f"- **Provenance:** extracted — `{prov.get('extractedFrom')}` (ran {prov.get('ranAtIso', 'n/a')})"
    elif prov_kind == "demo-sample":
        provenance_line = f"- **Provenance:** DEMO-SAMPLE — {prov.get('note', 'synthetic/demo data')}"
    else:
        provenance_line = "- **Provenance:** **MISSING** — this model fails G0 (fail-closed)"
    demo_banner = (
        "\n> ⚠️ **DEMO SAMPLE — NOT REAL TELEMETRY.** This model was built from synthetic/demo "
        "data (`provenance.kind = demo-sample`), not extracted from any tenant. Downstream "
        "consumers (renderers, run skills) refuse demo-sample models unless they are explicitly "
        "opted in (`--demo` / `WORKLOAD_MODEL_ALLOW_DEMO=1`). Do not use it to load-test anything.\n"
        if prov_kind == "demo-sample" else ""
    )

    risks = [
        "**R1 (sampling blindness).** Source sampling ratio = "
        f"{src.get('samplingRatio')} (`Sampled: no` on this tenant → unsampled). Rare / error / "
        "retry-storm journeys are still under-represented at extraction; weights reflect the "
        "observed window only. Error-rate baselines read 0.0 because no error spans fell in the "
        "window — not a guarantee of an error-free path.",
        "**R2 (mean ≠ peak).** This model captures *mean* arrival over the window. No peak-"
        "envelope / 'peak vs typical' profile exists yet (separate backlog). CoV is low here so "
        "mean ≈ peak is tenant luck, not a modeled guarantee.",
        "**R5 (instrumentation coverage / circular ground truth).** Extraction and later "
        "validation draw from the same telemetry; shared blind spots — async fan-out, Kafka "
        "consumers, websockets, fire-and-forget — are invisible on both sides. At least one run "
        "should be cross-checked against infra metrics (CPU/connections), not telemetry alone.",
    ]
    sic = src.get("sessionIdCoverage")
    if sic is not None:
        if sic.get("hasSessionSignal"):
            svc = ", ".join(
                f"`{s['service']}` {s['coveragePct']}% ({s.get('sessions', 0)} sessions)"
                for s in sic.get("services", []) if s.get("sessionSpans")
            )
            risks.append(
                "**R5 session signal (Path B — OTel `session.id` on spans).** "
                f"`session.id` coverage **{sic.get('overallCoveragePct')}%** across the reported "
                f"session-bearing services; present on: {svc}. Where present, journeys are stitched from real session "
                "chains (ordered actions + measured think-times) rather than span-order inference; "
                "elsewhere the span-order method (tiers 2a/2b) is the unchanged fallback. No RUM / "
                "classic-token dependency."
            )
        else:
            risks.append(
                "**R5 session signal (Path B).** No OTel `session.id` on any span in the window "
                "(0% coverage) → span-order session reconstruction (tiers 2a/2b) is the method; no "
                "session-stitch available on this target."
            )
    if risks_extra:
        risks.extend(risks_extra)
    risks_block = "\n".join(f"- {r}" for r in risks)

    return f"""# Scenario proposal: {meta['targetService']} rev {rev}
{demo_banner}
> Generated by the `workload-model` skill (SCOPE stage, methodology §3.1). Model file:
> `workload-model.json` (`{model['status']['hash']}`). This proposal is the **VALIDATE / Gate-V1**
> input — no synthesis or run may proceed until a human approves it and the approval is bound
> to model revision {rev}.

## What was analyzed
- **Target / front-end:** `{meta['targetService']}` (auto-discovered — see below)
- **Environment:** {meta['environment']}
- **Timeframe:** {src['timeframe']}
{provenance_line}
- **Exclusions:** {exclusions}
- **Coverage:** {spec['coverage'] * 100:.1f}% of application entry traffic
- **Evidence sources:** {', '.join(src.get('evidenceSources', []))}

{access_caveat}

## Journeys to be tested
| id | weight | entrypoint | codeRef | baseline p95 (ms) | evidence |
|---|---|---|---|---|---|
{journey_table}

## Arrival profile ({spec['arrivalProfile']['model']} model)
| duration | rate | shape |
|---|---|---|
{stage_rows}

**Little's Law check (server-side span, §3.1 step 5):** expected concurrency \
{llc['expectedConcurrency']} ≈ observed {llc['observedConcurrency']} → ratio **{llc['ratio']}** \
(band 0.5–2.0 ✓). Response-time term is the **front-end server span**, not the load-driver
wrapper — the wrapper bakes in think-time and would inflate concurrency by orders of magnitude.

## Payload strategy
{payload_block}

PII stance: synthetic payloads only; generators are PII-free by construction.{cache_pii}

## Where it will run
- **Target environment (allowlist):** {target_env}
- **Caps:** {json.dumps(spec.get('caps', {}))}
- {abort_note}

## Risks & unknowns
{risks_block}

## Decision requested
Approve as-is, or adjust: front-end choice (driver vs edge server), scenario merges /
weights, arrival rate/shape, caps, or abort thresholds. Approval must be recorded against
model revision {rev} (`{model['status']['hash']}`).
"""
