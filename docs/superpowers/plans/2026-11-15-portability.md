# Linux and macOS portability implementation plan

**Goal:** Finish the portability work authorized in the conversation and publish verified commits.

**Architecture:** Keep Windows Job Objects and POSIX process groups. Discover executable Claude installations per platform and report real containment failures. No new runtime dependencies.

**Constraints:** Python >=3.11; existing CLI and evidence format; never publish credentials. Continue in the existing checkout as authorized, including committing the existing portability changes.

## Tasks, in priority order

- [x] Verify and publish existing POSIX support; trigger the three-platform CI matrix.
- [ ] Inspect available Linux/macOS environments and authentication for an actual Claude smoke test. If unavailable, document exactly what remains unverified; do not copy personal credentials to hosted runners.
- [x] Add executable-discovery tests for POSIX fallback, symlinks and execution permissions; implement platform-aware candidates and errors.
- [x] Add failing regression tests for real permission errors during process-group cleanup; distinguish zombie-only groups and always reap the direct process on timeout/cancellation.
- [x] Exercise the real runner subprocess boundary using synthetic CLI processes, including successful completion, timeout and cancellation; run these on every CI platform.
- [x] Document Bash/Zsh installation, review, manual server/client usage and real Claude validation.
- [ ] Run the full suite and demo, review the diff, commit and push; inspect all three CI jobs and resolve failures.

## Review focus

Executables outside PATH; non-executable files; symlinks; permission failures mistaken for zombie groups; descendants surviving timeout/cancellation; no authenticated Claude environment on hosted CI.

## Progress

Initial support committed and pushed as 6dd75d7. Windows: 69 passed, 2 skipped; demo: plain kill leaves 2, contained termination leaves 0. Local WSL inventory contains docker-desktop only. Repository Actions secrets list is empty; no authenticated macOS host is available through the current tools.

Initial CI run 43755221054 passed on Windows, Ubuntu and macOS.
Regression tests reproduced missing POSIX fallback, swallowed kill permission errors,
and failure to reap the direct process when group termination fails, before fixes.
Final local Windows verification: 80 passed, 4 POSIX-only tests skipped; demo 2/0.
The authenticated Claude integration remains pending on Linux/macOS, with commands
documented in README.md. No credentials were transferred to hosted CI.
