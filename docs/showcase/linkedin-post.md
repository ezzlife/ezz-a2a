# LinkedIn post drafts

Every number below comes from this repository: `python -m ezz_a2a.demo` output,
`pytest` (250 passed, 4 skipped) and the file sizes. Re-run them before posting. The
repository is private, so the post links to nothing; offer the code on request.

## Main post (about 1,100 characters)

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

The gap I almost shipped: the worker ran for a moment before joining the job.
With the event loop held for 20 ms, 9 of 10 grandchildren escaped. Now it starts
suspended, joins the job, then resumes: 0 of 10.

What is the nastiest "the process is dead but not really" bug you have met?

#Python #Windows #AIAgents #A2A #SoftwareEngineering

## Short version (about 450 characters)

kill() on Windows ends one process, not its children. I measured it: with a
3-level process tree, a plain kill left 2 of 3 processes running; a Job Object
left 0.

I now run Claude Code workers inside one, and fail the request if the job
cannot be created. Port 0 + announce instead of a port race, evidence written
before printing, 250 tests with zero model calls.

The gap: a worker that runs before joining the job. Starting it suspended took
escapes from 9 of 10 to 0 of 10.

## Posting notes

- Attach a screenshot of the two-line demo output; it is the whole story.
- Post it as text plus one image. Links in the body lower reach.
- Reply to early comments within the first hour.
- Nobody can promise it goes viral. The hook (2 of 3 vs 0 of 3) is what makes
  it worth reading.
