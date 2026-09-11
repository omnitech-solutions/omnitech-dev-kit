# Cost model — what a unit costs, where the money goes, how to budget a campaign

Numbers below are from one pilot: 10 committed units on one feature, GLM 5.3 (planner) and GLM 5.3 Flash
(reader, implementer, verifier) through OpenRouter, OMP harness, 2026-09-10. Total **$0.98** for 10 units;
the single "one big model, one pass" attempt that preceded it cost **$1.05** and shipped nothing verifiable.

## Per-unit shape

| Role | Typical wall | Typical cost | What drives it |
| --- | --- | --- | --- |
| reader (Flash, r/o) | 40 s – 4 min | $0.00 – $0.02 | number of files named; a vendored bundle = timeout |
| orchestrator (mid model, r/o) | 6 s – 35 s (healthy) | $0.00 – $0.03 | length of evidence note; a 3-file read without line ranges = 4–6 min timeout at $0.01–$0.04 |
| implementer (Flash, worktree) | 1 – 10 min | $0.01 – $0.05 | whether it runs the full test bar (never should) |
| verifier (Flash, worktree) | 3 – 6.5 min | $0.006 – $0.03 | the full bar; the cost is mostly wall clock, not tokens |
| **unit, healthy** | 15 – 25 min | **$0.05 – $0.10** | evidence quality |
| unit with one timeout | +4–6 min | +$0.01 – $0.04 | wasted run |
| unit with a fix loop (R1/R2) | +10–15 min | +$0.03 – $0.10 | a design that had to be discovered live |

Range observed: $0.052 (FF-04, root cause named in the evidence note) to $0.179 (FF-05b, one planner timeout).

## Where the waste was
1. Wall-clock kills: every wasted dollar. Reader on a 40k-line bundle; implementer running full gates in 8 min;
   planner at 4–6 min on prompts that took seconds elsewhere.
2. Fix loops after a false green: not a model cost, a human-time cost (30–60 min each). Four of ten units.
3. Zero waste from the guards: neither the $0.25 per-run nor the $2.00 campaign cap ever fired.

## Rules that follow (all encoded in the promptbooks, RUNBOOK and run.py)
- Planner and reader are read-only and cheap; spend human minutes there, not model dollars.
- Implementer runs only the tests the packet names. Verifier owns the full bar with a 9–12 min cap.
- One timeout → change the prompt (line ranges, fewer files) or hand-write the artefact. Never re-run unchanged.
- Model tiering: Flash for everything that has a bar to check it (implementer, verifier, reader); a mid model only
  for the planner, and only when the evidence note does not already carry the design. A frontier model is never
  in the loop; it is the human's tool for evidence notes and probe cycles, billed to the human's own session.
- `usage_probe` must see the same key the harness bills. If it cannot (Claude Code, local models), `harness` or
  `none` is recorded and the wall clock is the only guard.

## Budgeting a campaign
```
units       = ledger rows you expect to open (count them; cap the ledger)
per_unit    = $0.10 healthy, $0.20 with one fix loop     (Flash-class workers)
campaign    = units × per_unit × 1.5 (timeouts, re-verifies)
campaign_cap_usd = round up to the next dollar; run_cap_usd = 2–3× the largest expected single run
```
Example: 8 rows → 8 × 0.10 × 1.5 = $1.20 → cap $2.00, run cap $0.25 (what the pilot used).
A campaign that approaches its cap is not a reason to raise the cap; it is a reason to read `spend.jsonl`
(`validate.py spend`) and find the timeouts.

## What scales the cost and what does not
- Cost scales with **number of runs**, not with feature size: bigger features mean more rows, not bigger rows.
  A row that needs more than one packet is two rows.
- Cost does not scale with parallelism: two units in flight cost the same as two in sequence. Human review time
  does scale, and that is the real ceiling (one person reviews ~one unit per 25–40 min).
- Switching harnesses does not change the per-unit shape; it changes the cost source and the boundary
  mechanism (see HARNESSES.md). Local models via OpenCode/LM Studio bring cost to $0 and move the entire
  budget to wall clock.
