# utilities

Standalone, dependency-free Python CLIs extracted from the `workload-model` skill (SCOPE
step 2c session signals). Each is a single file: pure, deterministic functions plus a thin
CLI. **No telemetry I/O** — you run the DQL against your own tenant (see each tool's
`--help` for the exact query) and feed the rows in via file or stdin.

| Tool | What it does | Input |
|---|---|---|
| `rum_sessions.py` | RUM session **shape** (actions/duration/bounce distributions) + per-app coverage from Dynatrace Grail `user.sessions` | DQL record rows (JSON array) |
| `session_stitch.py` | Stitches sessions from OTel `session.id` on spans: ordered chains, **measured inter-action think-times**, session boundaries, coverage report | DQL record rows (JSON array) |

## Usage

```bash
# RUM session shape (rows from: fetch user.sessions ...)
python3 utilities/rum_sessions.py shape   < rum_rows.json
python3 utilities/rum_sessions.py cover   < per_app_rows.json

# Session stitching (rows from: fetch spans | filter isNotNull(session.id) ...)
python3 utilities/session_stitch.py stitch < span_rows.json
python3 utilities/session_stitch.py stitch < span_rows.json --max-gap-s 1800
python3 utilities/session_stitch.py cover  < coverage_rows.json
```

Run `python3 utilities/<tool>.py --help` for the exact DQL to run and the row shapes.

## Notes

- Both tools are also shipped inside `skills/workload-model/scripts/` where the full SCOPE
  pipeline consumes them; the copies are kept identical (the utility adds only the CLI).
- `user.events` (ordered per-action RUM navigation) needs the OAuth scope
  `storage:user.events:read`; `user.sessions` typically works with a plain read token.
- Scrub PII (geo / user / IP) from any RUM field before committing rows to a repo.
