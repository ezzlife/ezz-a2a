# LinkedIn post drafts

Every number below comes from this repository: `python -m ezz_a2a.demo` output,
`pytest` (250 passed, 4 skipped) and the three recorded runs of
`cases/records-known-findings` in `evidence/`. Re-run them before posting. The
repository is public at https://github.com/ezzlife/ezz-a2a; the link goes in the first
comment, not in the body.

## Main post (about 900 characters, paste as is)

Line breaks and symbols are deliberate: LinkedIn shows the text exactly as
pasted, and short lines are what keep it readable on a phone.

```text
🤔 Your AI agent times out and you kill it. Is it really dead?

On Windows, probably not. 🧟

📍 The problem
kill() stops one process, not its children. I measured it with a claude.exe → node → tool tree:
❌ Plain kill: 2 of 3 processes still alive

🛠️ The context
I hit this building ezz-a2a, a small A2A agent that hands code reviews to Claude Code. A review that times out must not leave workers running in the background.

✅ The solution
A Windows Job Object with KILL_ON_JOB_CLOSE:
→ Timeout, cancel or crash: 0 of 3 left alive
→ The worker starts suspended and joins the job before it runs. Without that, 9 of 10 grandchildren escaped. Now 0 of 10. 🔒

🎯 And the reviews? On a 2018 snapshot of kennethreitz/records: 5 of 5 known bugs found, 0 of 3 false alarms, in 3 of 3 runs.

💬 What's the nastiest "dead but not really" bug you've met?

👇 Code in the first comment

#Python #Windows #AIAgents #SoftwareEngineering
```

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
