# Review token reduction

## Goal

Lower the tokens and cost of each review without losing real findings. The worker keeps `--tools ""` and `--max-turns 1`.

## Measured starting point

Source: two runs on a private repository (5 and 2 files of its SQL query builders). Those
evidence files hold that repository's code, so they are not published; the figures below
are copied from them.

| | 5 files | 2 files |
|---|---|---|
| output tokens | 10 690 | 11 269 |
| cache_creation | 22 611 | 12 252 |
| cache_read | 0 | 1 710 |
| cost (USD) | 0.197 | 0.162 |

- Output dominates the cost. Cutting 5 files to 2 saved 18 % and made the reviewer mark helpers it could not see as unverified.
- Nothing measures whether a change loses real findings, so the known-findings case ships first.

## Known-findings case (records at `f2c5307`)

The case was first built on that private repository. It now lives in
`cases/records-known-findings/`: `records.py` from the public, ISC-licensed
`kennethreitz/records` as of 2018-02-15, copied unmodified under `source/`. Every real finding
was later fixed or reported upstream, so the answer key comes from the project's history.

Real findings (all in `records.py`):

- **R1** `:149`: `rows[2:]` evaluates `len(self) < None` before the `None` check and raises `TypeError` on Python 3 (fixed in `d47f7b8`).
- **R2** `:314-315,326-327`: `Database.query` returns a lazy `RecordCollection` from inside `with self.get_connection()`, so the connection closes before the rows are read (issue #149, PR #190).
- **R3** `:344-345`: `Database.transaction` rolls back in a bare `except` and never re-raises (PR #230).
- **R4** `:513-514`: the CLI prints binary exports with `print()`, so Python 3 writes the `b'...'` repr (issue #78).
- **R5** `:481,513-514`: `<format>` is never validated; `supported_formats` is unused and a `key=value` parameter without a format becomes the format (issue #133).

Known false findings:

- **F1** "`Connection.query` is SQL injection": the query is the caller's SQL by design and values are bound through `**params` at `:377`.
- **F2** "`StopIteration` escapes `__iter__` (PEP 479)": it is caught at `:126` and turned into `return`.
- **F3** "`one()` never checks for a second row": it reads `self[1]` and raises `ValueError` at `:240-250`.

## Metric

Per run: real findings found (of 5), known false findings flagged (of 3), output tokens, cost and `cache_read_input_tokens`, from `artifacts[].metadata` (null where the CLI reports nothing). Matching findings to the case uses anchor terms and line ranges, which is approximate; disputed matches are adjudicated by reading the text.

A change that lowers tokens but loses a real finding is reverted.

## Changes, one pull request each

1. **Case and metric.** `cases/records-known-findings/`, a pure scorer and a before/after report. Baseline: 5-file and 2-file runs.
2. **Automatic context.** Without an LLM, resolve imported Python symbols defined outside the listed files and attach only their definitions, honouring the source exclusions and `MAX_PROMPT_CHARACTERS`.
3. **Output cap.** Ask for at most N short findings (file, line, scenario, fix), no summary. This is the only change to the response text.
4. **Verification.** A second, cheaper tool-less call checks each finding against the cited code. Discards are recorded in `artifacts[].metadata.verification`; the response text is unchanged. It adds a call, so it stays only if it discards F1-F3 without losing R1-R5.
5. **Cache.** Stable prefix (instructions, task, then sources); measure `cache_read_input_tokens` across repeated runs. It stays only if the measurement shows a gain.
6. **Refuted findings registry.** The coordinator stores findings that verification discarded, keyed by the sha256 of the cited sources, and injects "already refuted" into later reviews of unchanged code. Stale entries expire.

## Rules

- TDD with a fake Claude process; no quota is spent by the tests. Each new test must fail first for the right reason.
- No file over 300 lines, named constants, no dead code or needless comments.
- Own branch and pull request per step, green CI before merging.
- Real runs cost roughly USD 0.15-0.20 each; the whole plan about 8-10 runs.
