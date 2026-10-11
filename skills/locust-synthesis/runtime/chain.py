# chain.py — request-chaining / correlation helpers (G2, methodology §3.3 rule 3).
#
# Pure, dependency-free Python so it is importable BOTH from a generated locustfile
# AND from unit tests. `extract()` reads from a requests.Response-like object
# (`.json()`, `.headers`, `.text`); the generated step wraps every extraction in
# `require_value()`, which raises BrokenChainError on a null correlation so the
# journey iteration aborts immediately — the Locust equivalent of k6's `fail()`
# ("fail the chain on broken correlation").

import re


class BrokenChainError(Exception):
    def __init__(self, step_id, var_name):
        super().__init__(
            f"broken chain at step={step_id}: correlation {var_name} extracted null"
        )
        self.step_id = step_id
        self.var_name = var_name


def resolve_path(obj, path):
    """Resolve a dotted / bracketed / JSONPath-ish path against a parsed object.
    "products[0].id" and "$.id" both work. Returns None (never raises) on any miss."""
    if obj is None or not isinstance(path, str) or path == "":
        return None
    norm = re.sub(r"\[(\d+)\]", r".\1", path)  # products[0] -> products.0
    norm = norm.lstrip("$").lstrip(".")  # tolerate a leading JSONPath "$."
    segments = [s for s in norm.split(".") if s]
    cur = obj
    for seg in segments:
        if isinstance(cur, list):
            try:
                idx = int(seg)
            except ValueError:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            if seg not in cur:
                return None
            cur = cur[seg]
        else:
            return None
    return cur


def _ci_get(headers, name):
    """Case-insensitive header lookup over a dict-like headers object."""
    want = str(name).lower()
    try:
        items = headers.items()
    except AttributeError:
        return None
    for k, v in items:
        if str(k).lower() == want:
            return v
    return None


def _cookie_value(set_cookie, cookie_name):
    """Pull a single cookie value out of a Set-Cookie header string."""
    for part in str(set_cookie).split(";"):
        kv = part.strip().split("=", 1)
        if len(kv) == 2 and kv[0] == cookie_name:
            return kv[1]
    return None


def extract(res, spec):
    """Extract a correlation value from a response-like object.
    spec = { from: body_json|header|body_html|body_regex, path }.
    Returns None on any failure — the caller MUST treat None as a broken chain."""
    if res is None or spec is None:
        return None
    frm = spec.get("from")
    path = spec.get("path")
    try:
        if frm == "body_json":
            body = res.json()
            return resolve_path(body, path)
        if frm == "header":
            headers = getattr(res, "headers", None) or {}
            # support a "set-cookie:session" style path -> header then cookie name
            if ":" in str(path):
                hname, sub = str(path).split(":", 1)
                raw = _ci_get(headers, hname)
                return _cookie_value(raw, sub) if raw is not None else None
            return _ci_get(headers, path)
        if frm == "body_html":
            # path = "left||right"; returns text strictly between the two markers.
            body = getattr(res, "text", None) or ""
            parts = str(path).split("||")
            if len(parts) != 2:
                return None
            left, right = parts
            start = body.find(left)
            if start < 0:
                return None
            start += len(left)
            end = body.find(right, start)
            if end < 0:
                return None
            return body[start:end]
        if frm == "body_regex":
            body = getattr(res, "text", None) or ""
            m = re.search(str(path), body)
            return m.group(1) if (m and m.lastindex) else None
    except Exception:
        return None
    return None


def require_value(value, step_id, var_name):
    """Return value, or raise BrokenChainError when it is None. The generated
    journey lets this propagate so Locust aborts the iteration and records the
    failure — the fail-fast broken-chain contract (§3.3 rule 3)."""
    if value is None:
        raise BrokenChainError(step_id, var_name)
    return value
