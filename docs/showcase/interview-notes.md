# Interview notes: ezz-a2a

Two-minute pitch, then the questions a technical interviewer is likely to ask.
Every claim points at code or a measurement you can open during the call.

## Two-minute pitch

A local A2A 1.0 agent (Python, official SDK 1.3.0) that takes a task file
listing source files, starts a throwaway server on localhost, sends the task
through the protocol, runs `claude -p` with no tools, and saves the answer plus
an evidence file. Claude sees only the files you list and cannot edit anything.

The interesting part is not the happy path. It is what happens when things go
wrong: timeouts, crashes, a closed console, a full disk, a hostile source file.

## Questions and answers

**Why a Job Object and not `process.kill()` or psutil?**
`kill()` ends one process; its children survive. I measured it:
`python -m ezz_a2a.demo` prints 2 of 3 processes left after a plain kill
and 0 of 3 with the job. A job with KILL_ON_JOB_CLOSE also ends the tree if the
server itself dies, because the handle belongs to the server (`ezz_a2a/claude/windows_job.py`).
A psutil walk would race against processes spawning while you walk.

**What does it not cover?**
It used to have a gap: the worker ran before it joined the job, and a child
spawned in that window escaped. With the event loop held for 20 ms, 9 of 10
grandchildren escaped. asyncio exposes no thread handle, so the fix starts the
process with `CREATE_SUSPENDED`, assigns it and resumes it with `NtResumeProcess`:
0 of 10 (`tests/claude/test_windows_job.py`). On Linux/macOS it is a process group,
which does not end if the worker crashes and can be escaped with a new session.

**What happens if the job cannot be created?**
Fail closed: the process is killed and the request ends as failed
(`ezz_a2a/claude/runner.py`, `tests/claude/test_runner_tree.py::test_uncontainable_worker_is_killed_and_never_answers`).

**How do you avoid a port race?**
The server binds port 0 itself and prints `A2A_PORT=<n>`; the launcher reads it
(`ezz_a2a/worker/cli.py`, `ezz_a2a/review/local_service.py`). No "find a free port, release it, hope".

**How do you test it without paying for model calls?**
Synthetic processes and a real separate server over localhost. The gate is
`scripts/pre-push.sh` on Windows, so the Job Object tests execute instead of
skipping. 250 tests pass, 4 skip.

**How do you protect secrets?**
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the server's own `A2A_TOKEN` are
removed from the worker environment; alternative providers are rejected;
exception text is never stored in evidence, only its type; the server compares
the bearer token with `hmac.compare_digest`.

**What if the output file already exists, or saving fails after a paid call?**
Evidence is staged in a hidden file, written and fsynced before printing, then
published with a hard link so an existing file is never replaced. Exit code 3
means "review ran, evidence not saved" and names the kept file
(`ezz_a2a/review/evidence.py`, `ezz_a2a/review/cli.py`).

**Why does the review have exit codes 0/1/2/3/130?**
So a script can tell apart "review failed", "bad input, nothing sent",
"result not saved" and "interrupted".

**How was it reviewed?**
By other models: Sonnet, Fable and Codex reviewed the code, and the main
session decided which findings to accept.Say plainly that the model reviews are input, not proof.

## Honest limits to volunteer

- One request at a time, 180 s timeout, state in memory.
- No streaming, remote cancel or retries.
- Not an OS sandbox; it does not measure remaining quota.
- Hard-link publication needs a filesystem that supports them.

## Questions to ask back

- How do you stop agent-spawned subprocesses today?
- Do you run model-backed tests in CI, and who pays for them?
