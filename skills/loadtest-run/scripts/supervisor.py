"""Caps / abort supervisor for the full run (methodology §7, §3.4.2 rule 2).

The supervisor is handed each runtime sample as the k6 run progresses. It enforces
two independent kinds of limit:

* **Hard caps** (§7.2): max RPS, max VUs, max duration. These bound the blast radius.
* **Abort thresholds** (§3.4.2 rule 2): error-rate / p95 / p99 ceilings that trip a
  kill when the system under test starts failing.

Any breach of either trips an abort and invokes the injected ``teardown`` callback
exactly once (safe teardown), recording the cause for the run-report (§7.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Sample:
    elapsed_s: float
    rps: float
    vus: float
    error_rate: float
    p95_ms: float
    p99_ms: Optional[float] = None


def _dur_to_seconds(spec: str | int | float) -> float:
    """Parse a k6-style duration (``30m``, ``90s``, ``1h30m``) or a raw number of seconds."""
    if isinstance(spec, (int, float)):
        return float(spec)
    s = str(spec).strip()
    if not s:
        return 0.0
    units = {"h": 3600, "m": 60, "s": 1}
    total, num = 0.0, ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch in units:
            total += float(num or 0) * units[ch]
            num = ""
        else:
            raise ValueError(f"unparseable duration: {spec!r}")
    if num:  # bare number => seconds
        total += float(num)
    return total


@dataclass
class Supervisor:
    caps: dict[str, Any]
    abort: dict[str, Any]
    teardown: Callable[[str], None] = lambda reason: None

    aborted: bool = False
    abort_reason: Optional[str] = None
    _torn_down: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self.max_rps = self.caps.get("maxRps")
        self.max_vus = self.caps.get("maxVus")
        self.max_duration_s = (
            _dur_to_seconds(self.caps["maxDuration"]) if "maxDuration" in self.caps else None
        )

    def _breach(self, sample: Sample) -> Optional[str]:
        # Hard caps.
        if self.max_rps is not None and sample.rps > self.max_rps:
            return f"cap:maxRps rps={sample.rps:.1f}>{self.max_rps}"
        if self.max_vus is not None and sample.vus > self.max_vus:
            return f"cap:maxVus vus={sample.vus:.0f}>{self.max_vus}"
        if self.max_duration_s is not None and sample.elapsed_s > self.max_duration_s:
            return f"cap:maxDuration elapsed={sample.elapsed_s:.0f}s>{self.max_duration_s:.0f}s"
        # Abort thresholds.
        er = self.abort.get("errorRateGt")
        if er is not None and sample.error_rate > er:
            return f"abort:errorRateGt error_rate={sample.error_rate:.3f}>{er}"
        p95 = self.abort.get("p95MsGt")
        if p95 is not None and sample.p95_ms > p95:
            return f"abort:p95MsGt p95={sample.p95_ms:.0f}ms>{p95}ms"
        p99 = self.abort.get("p99MsGt")
        if p99 is not None and sample.p99_ms is not None and sample.p99_ms > p99:
            return f"abort:p99MsGt p99={sample.p99_ms:.0f}ms>{p99}ms"
        return None

    def observe(self, sample: Sample) -> str:
        """Feed one runtime sample. Returns ``"continue"`` or ``"abort"``.

        On the first breach the injected teardown runs exactly once and the
        supervisor latches aborted; subsequent samples short-circuit to ``abort``.
        """
        if self.aborted:
            return "abort"
        reason = self._breach(sample)
        if reason is None:
            return "continue"
        self.aborted = True
        self.abort_reason = reason
        self._safe_teardown(reason)
        return "abort"

    def _safe_teardown(self, reason: str) -> None:
        if self._torn_down:
            return
        self._torn_down = True
        self.teardown(reason)
