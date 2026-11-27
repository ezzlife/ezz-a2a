# Review context formats implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation and a final independent review.

**Goal:** Review configuration, SQL, contracts, scripts and build files while excluding sensitive and known generated inputs by default.

**Architecture:** Extend the existing explicit source filter; validate requested and resolved paths. Permit only direct YAML files in the root `.github/workflows/` as an exception to hidden-path rejection. Keep snapshots and the transport unchanged.

**Tech Stack:** Python 3.11+, pathlib, pytest; no new dependencies.

**Spec:** The user's approved expansion in this conversation. Orchestrator/provider routing is future work, not part of this change.

## Global constraints

- Preserve the prior language expansion and current uncommitted changes.
- Preserve UTF-8, relative paths, repository boundaries, evidence/task exclusions and the 100,000-character prompt limit.
- No Claude calls, external publication or runtime integration.
- Add `.yaml`, `.yml`, `.toml`, `.jsonc`, `.sql`, `.prisma`, `.graphql`, `.gql`, `.proto`, `.sh`, `.bash`, `.ps1`, `.xml`, `.properties`, `.gradle`, `.kts`, `.tf`, `.hcl`.
- Allow exact names `Dockerfile`, `Containerfile`, `Makefile`, `Jenkinsfile`, `go.mod`, `go.sum`.
- Block known dependency/output directories and generated/minified filename patterns; do not claim universal generated-file or secret detection.
- Reject NUL-bearing sources as binary even when they decode as UTF-8.

## Review focus

- Requested workflow paths and resolved destinations must both satisfy the hidden-path policy.
- Links must not disguise generated directories or filenames.
- Extra extensions must not admit keys, certificates, archives or executable binaries.
- Ordinary manifest names must remain allowed, including Go checksums.
- Hidden workflow exception must not admit nested or non-YAML files.

### Task 1: Expand and verify the source policy

**Files:** `ezz_a2a/review/task.py`, `tests/review/test_review_formats.py`, `tests/review/test_review_scope.py`, `README.md`.

**Interfaces:** `prepare_review(task_file, repository)` keeps its current return contract and preflight errors.

- [x] Add real-file tests for accepted formats, prohibited paths and binary contents.
- [x] Run the focused tests and observe failures for missing behavior.
- [x] Extend path validation and reject NUL-bearing source content.
- [x] Document exact supported formats, workflow exception and exclusions.
- [x] Run `.venv/Scripts/python.exe -m pytest` and `git diff --check`.
- [x] Obtain an independent review and address concrete defects.
- [x] Leave changes local for the user, with verified results recorded below.

## Progress

Plan recorded before implementation. Existing language changes are retained.

RED: new accepted formats and generated/binary restrictions failed against the old filter.
GREEN: full suite 173 passed, 4 skipped; `git diff --check` passed.
Independent read-only review: approved with no defects; reviewer also ran 101 focused tests successfully, including Windows junction cases.
Scope decisions: no universal secret/generated detection, provider routing or extra framework tooling. Existing concurrent filesystem mutation/hard-link provenance limitations are unchanged. Only Windows execution was verified locally; this uncommitted change has not run in remote CI. The referenced global harness instructions remain unavailable.
Changes remain local and uncommitted; no publication or quota-consuming Claude call was performed.
