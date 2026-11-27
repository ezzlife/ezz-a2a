# Review lessons: errors found once become checks that run without a model

## Problem

Every review starts from zero: the worker runs with no memory and no session. A defect that
a review found, or a false claim that a review made, is forgotten on the next run, so the
same tokens are spent again. A language model cannot be relied on to remember; the
coordinator can.

## Design

A *lesson* is a small deterministic detector with a test. It is a Python function that
receives one hashed source and returns the places where a known defect pattern appears.
The coordinator runs every lesson over the listed sources before the model is called and
attaches the hits to the prompt under `context.lessons`, each with path, lines, the lesson
id and a one-line description. The reviewer confirms or dismisses each hit instead of
discovering it, and the evidence records the hits.

Lessons live in `ezz_a2a/review/lessons/`, one file per lesson, registered in a list. A
lesson is added only when a review found a real defect (or a false claim worth blocking)
and a failing test shows the pattern.

First lessons, taken from the first known-findings case (built on a private repository,
since replaced by `cases/records-known-findings`):

- `like-without-escape`: an SQL `LIKE` whose pattern is built from input and has no
  `ESCAPE` clause.
- `order-by-without-tiebreaker`: a paginated query (`LIMIT`/`OFFSET`) ordered by a
  single non-unique column.
- `path-from-argv` (this repository, SonarCloud twice): `ast` finds a name assigned from
  `argparse` results reaching `open`, `read_text` or `read_bytes`.

## Rules

- No model call, no tools: it is plain Python on the sources already in the prompt.
- Hits are evidence, not verdicts: the instructions say to verify each and to say when one
  is a false positive.
- The prompt limit still applies: hits are trimmed last and counted in `context.lessons_omitted`.
- A lesson that produces a false positive on the known case is removed or tightened.

## Measurement

Against `cases/records-known-findings`: `real_found` must not drop, `false_flagged` must not
rise, and output tokens should fall because the reviewer spends less on discovery. The
coordinator alone knows the hits, so they are recorded in the evidence under `context.lessons`,
not in `artifacts[].metadata`, which the worker writes.

## Out of scope

Learning from a user's rejections (the refuted-findings registry, PR6 of the token plan)
and lessons for languages other than Python and SQL strings.
