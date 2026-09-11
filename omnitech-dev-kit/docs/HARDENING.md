# Hardening — what the control layer refuses, and what it still cannot promise

Date: 2026-09-10. Applies to kit v0.2.x after the first live multi-harness trial.

Two inputs produced this pass: an offline review of v0.2.0 that reproduced 28 contract weaknesses, and a
live trial that ran the same reader question through all four harnesses and found three more. Everything
below is implemented and exercised; the "not promised" section is the part that is still honest to doubt.

## The principle

**A boundary the harness cannot enforce is not a boundary, and a measurement that failed is not a zero.**

Every check that can run without a model now runs before the model starts. A check that cannot be made
true is surfaced as a refusal or an explicit unknown, never as a silent default.

## Exit codes — each one is a stop, never a retry signal

| exit | meaning | when it fires |
| --- | --- | --- |
| 0 | the run completed and any declared artefact validated | — |
| 2 | usage error: unknown option, `--validate` without `--out`, an explicit `--config` that does not exist | before launch |
| 3 | this run cost more than `run_cap_usd` | after the run; the money is already spent |
| 4 | campaign over `campaign_cap_usd` | **before launch** (admission) and after the run (report) |
| 5 | the produced artefact failed shape or consistency validation | after the run |
| 6 | the prompt would not fit the model's declared context window | before launch |
| 7 | the harness cannot enforce a boundary this role requires | before launch |
| 8 | an implementer was pointed at the primary checkout instead of a worktree | before launch |
| 9 | the run could not be metered and `allow_unmetered` is not set | before launch |
| 78 | (OpenCode adapter) the role agent file is missing, so tool limits cannot be applied | before launch |
| 124 | wall clock: the process tree was killed at the cap | during |
| 125 | loop watchdog: one tool call repeated past the threshold, tree killed early | during |

## What changed

### Admission happens before spending
Budget, metering, capability, worktree, context and option checks all run before the adapter is executed.
The campaign total is computed from the campaign's own `spend.jsonl`, so it works for harness-reported
costs where a provider usage probe says nothing. The old per-run and per-campaign checks remain, but they
are now labelled for what they are: **overrun reports**, fired after the money is committed.

### Every started run leaves a record
A `runs/<ts>-<role>-<unit>.run.json` record is written before launch and finalised on every exit path. A
failed cost probe no longer loses the spend row; the row is written with `cost_known: false` and the
probe error. **Unknown cost is recorded as unknown, never as `$0.00`**, and unknown rows are excluded from
campaign totals and counted separately.

### The capability contract
`HARNESS_CAPS` in `run.py` records what each harness can actually enforce, not what it can be asked to do.
A role that excludes shell on a harness that cannot remove shell is refused (exit 7) unless the gap is
written down in `kit.config.json` under `allow_capability_gap.<harness>`. Session persistence is a warning
rather than a refusal: it weakens reproducibility but cannot let a role exceed its scope.

Codex's sandbox is now chosen from the role's `writes` flag, not from whether `bash` appears in its tool
list. A verifier needs shell to run gates and must still not be able to edit the candidate it is judging.

### The process tree is killed, not just the wrapper
The adapter runs in its own process group (`start_new_session`) and timeouts and watchdog kills signal the
whole group, then confirm it is gone. Killing only the wrapper left the model CLI running and billing.
Local process termination is still not the same as remote cancellation; see below.

### Loop and context defences
A watchdog polls the log during the run and kills at the eighth repeat of one tool call (exit 125) instead
of burning the full cap. A pre-flight refuses a prompt that would not fit the model's declared window.
`analyze_run.py` understands omp, OpenCode and Codex log shapes, and reports **"loop detection unavailable"**
for a harness whose log carries no tool lines rather than implying a clean run.

### Validators check consistency, not only shape
An ACCEPT receipt contradicted by a failed gate line is now invalid, as is a receipt stating both verdicts.
An honest REJECT carrying a failed gate stays valid — that is a truthful document and must remain
representable. The gate pattern accepts the `(PASS)`/`(FAIL)` suffix the gate helper actually emits. Packet
sections must carry content rather than template placeholders. Ledger verdicts must be from the declared
set, which now includes `NOT REPRODUCED`, an outcome the pilot genuinely needed.

**Validation means the document is well formed and does not contradict itself. It never means the work is
accepted.** `validated: true` and exit 0 say the invocation succeeded and the shape held, nothing more.

### Paths, packaging and transport
Every `@file` is resolved to an absolute path before the adapter sees it, so a file that passes pre-flight
in the caller's directory cannot be unreadable from the worktree. `kit.config.example.json` now lives
inside the plugin root, so an installed plugin can scaffold. Generated commands name their config
explicitly. The apply recipe stages the worktree first, because a bare `git diff` silently drops every new
file, and a new test is the usual casualty.

### Skill distribution
Sync compares whole trees by content hash, records what it installed in `.kit-owned.json`, and refuses to
overwrite a destination it does not own — a borrowed skill will not clobber your own skill of the same
name. `--dry-run` now touches nothing, including the target directory. The compatibility checker fails when
the upstream runtime block is absent instead of skipping the check, and it checks borrowed skill names for
collisions because sync installs those too.

## What is still not promised

- **Spending is guarded, not capped.** Admission refuses the next run; it cannot stop a run already in
  flight, and a shared-key before/after delta cannot attribute cost correctly when runs overlap. Do not
  rely on these numbers for concurrent runs.
- **Killing local processes is not cancelling remote generation.** A killed run may still be billed.
- **A worktree is change isolation, not security isolation.** A role with shell can read anything the user
  can read. The kit narrows what a role is *given*, not what the machine permits.
- **Shape validity is not acceptance.** There is still no machine-checked lifecycle binding a verdict to a
  packet revision, fixture identity, base revision and candidate digest. That is the next design step, not
  something this pass delivered.
- **Gate lines are still model-written prose.** The verifier re-runs the gates, but the kit does not yet
  execute them itself and record the result independently.
- **The learning loop is not wired to crux.** The kit writes its own `forge-log.md`; that file is not where
  crux's retrospective looks. Matching the format is not the same as being discoverable.
