---
name: omnitech-dev-kit
description: Use when driving a system toward parity with a reference system one verified unit at a time - capturing fixtures, writing packets, running guarded workers in worktrees, verifying at the live boundary, and accepting. Triggers on "next unit", "kit next", "parity", "match the reference", "drive to green".
---

# Driving one unit to green

The loop is one command, `kit next`, plus the judgement only you can supply. Run `kit next`, read
what it says, do that, run it again. It never guesses past a human gate.

## Your job at each stage

**capture** — Drive both systems yourself and write two fixtures. Measured values only: computed
styles, DOM counts, element geometry before and after. "Looks right" is not a fixture. The reference
system is observe-only: no sends, publishes, saves, deletes or settings changes, ever.

**packet** — `kit next` drafts `packets/<id>.md` from the template in zero seconds for zero dollars.
You fill the blanks. Name the root cause, the exact insertion point, the one test, and at least
three tempting additions that are out of scope. §2 "owned files" is an exclusive scope: a worker
touching anything else is a scope breach. This is where cost is decided — a precise packet lands
for about $0.05, a vague one has cost $1.03 and produced broken output.

**execute** — `kit next` runs it: worktree chained from the last accepted branch, implementer under
a cap and a wall clock, deterministic gates, then a one-turn verifier. This is the only paid step.
A timeout means the packet was wrong, not the prompt: fix the packet, do not re-run it unchanged.

**verify** — The verifier's ACCEPT is a claim. Close the row yourself, in this order: the gate
record; the diff against §2; the test itself (would it pass without the change?); a mutation test
(copy the file aside, break the change, the test must go RED, restore byte-identical); then the
behaviour on the running system, with your own eyes. Write `receipts/<id>-live.md` starting with
`LIVE: PASS` and carrying `evidence:` lines. `kit accept` refuses without it, and that refusal has
caught a green receipt over a broken page four times in nine units.

**accept** — `kit next` commits and tags on the task branch and files the note. Then report to the
human in about ten lines: what changed, gate counts, cost, wall clock, what you verified yourself,
and anything you left open.

## Never

Author a packet with a model. Commit from the primary checkout while a worktree is dirty. Raise a
cap to make a run pass. Widen a packet's scope to avoid stopping. Let a worker open a browser.
