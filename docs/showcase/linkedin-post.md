# LinkedIn post drafts

Every number below comes from this repository: `python -m ezz_a2a.demo` output,
`pytest` (250 passed, 4 skipped) and the three recorded runs of
`cases/records-known-findings` in `evidence/`. Re-run them before posting. The
repository is public at https://github.com/ezzlife/ezz-a2a; the link goes in the first
comment, not in the body.

## Main post (about 1,800 characters)

Your AI agent times out. You kill the process. Its children keep running.

On Windows, `kill()` stops one process, not its tree. I measured it with a
three-level stand-in for claude.exe -> node -> tool:

- plain kill of the root: 2 of 3 processes still running
- Job Object terminate: 0 of 3

I hit this building a small A2A agent that hands a code review to Claude Code
over localhost. The fix is a Windows Job Object with KILL_ON_JOB_CLOSE: the
timeout, a cancellation and even a crash of the server end the whole tree. If
the job cannot be created, the request fails instead of running uncontained.

Three more decisions I would defend in a design review:

1. The server binds port 0 and announces the port it got, so there is no
   "pick a free port, then hope" race and the bearer token only reaches the
   right process.
2. Evidence (task, SHA-256 of every source, model, timestamps, response) is
   written before anything is printed and never overwrites a file, so a closed
   console cannot lose a paid answer.
3. 250 tests run on Windows without a single real model call.

Does the review itself work? I took records.py from kennethreitz/records as it
was in February 2018, when it still had five bugs that were fixed upstream
later, plus three plausible-looking false ones. In 3 of 3 runs with Claude
Sonnet it found all 5 real bugs and flagged none of the 3 false ones. One
caveat: an old, popular repository may be in the model's training data.

The gap I almost shipped: the worker ran for a moment before joining the job.
With the event loop held for 20 ms, 9 of 10 grandchildren escaped. Now it starts
suspended, joins the job, then resumes: 0 of 10.

What is the nastiest "the process is dead but not really" bug you have met?

#Python #Windows #AIAgents #A2A #SoftwareEngineering

## Short version (about 600 characters)

kill() on Windows ends one process, not its children. I measured it: with a
3-level process tree, a plain kill left 2 of 3 processes running; a Job Object
left 0.

I now run Claude Code workers inside one, and fail the request if the job
cannot be created. Port 0 + announce instead of a port race, evidence written
before printing, 250 tests with zero model calls.

The gap: a worker that runs before joining the job. Starting it suspended took
escapes from 9 of 10 to 0 of 10. And the reviews: 5 of 5 known bugs, 0 of 3
false alarms, in 3 runs on a 2018 snapshot of kennethreitz/records.

## Posting notes

- Attach `docs/assets/ezz-a2a-flow.png`: the 2 of 3 vs 0 of 3 panels plus the
  5 of 5 results band.
- Post it as text plus one image. Links in the body lower reach, so put
  https://github.com/ezzlife/ezz-a2a in the first comment.
- Reply to early comments within the first hour.
- Nobody can promise it goes viral. The hook (2 of 3 vs 0 of 3) is what makes
  it worth reading.
