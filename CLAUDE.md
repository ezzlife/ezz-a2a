# ezz-a2a

Local A2A 1.0 agent that sends a review task to `claude -p` (no tools, one turn)
and returns the answer as an artifact plus a JSON evidence file. Usage lives in
`README.md`; this file is for working on the code.

## Layout

- `ezz_a2a/claude/`: runner, CLI discovery, usage metrics, process containment
  (`windows_job.py` on Windows, `process_group.py` on POSIX).
- `ezz_a2a/worker/`: A2A server and executor (one request at a time, `asyncio.Lock`).
- `ezz_a2a/client/`: A2A client CLI.
- `ezz_a2a/review/`: task loading, source resolution, automatic context,
  deterministic `lessons/` detectors, evidence, scoring and `measure`.
- `ezz_a2a/demo/`: process-tree containment demo.
- `tests/` mirrors the package. `cases/` holds known-findings cases,
  `tasks/` task files, `evidence/` saved runs (generated records: do not edit).

## Checks

`scripts/pre-push.sh` is the local CI: pytest, `pyflakes ezz_a2a tests` and the
demo, on the Python 3.11 venv in `.venv`. Install it as `.git/hooks/pre-push`.
GitHub Actions runs only on `windows-latest`; when it cannot run, the local
script is the gate.

## Rules

- All code, docs and commit messages in English.
- No comments: clear names instead. Source files stay under 300 lines
  (`tests/test_source_size.py`). No dead code (pyflakes before closing).
- Named constants for timeouts, limits and exit codes; shared ones in
  `ezz_a2a/settings.py`.
- Paths opened by a CLI come from a `glob` of a known directory, never straight
  from argv (SonarCloud security rating; `tests/test_argv_paths.py`).
- Tests never call Claude. A change that claims fewer tokens or better findings
  is measured against `cases/records-known-findings` (an unmodified 2018 ISC file
  from `kennethreitz/records` in its `source/`) with
  `python -m ezz_a2a.review.measure before.json after.json --case records-known-findings`;
  what measures worse is discarded.
- Real Claude runs spend quota: run them only when asked.
