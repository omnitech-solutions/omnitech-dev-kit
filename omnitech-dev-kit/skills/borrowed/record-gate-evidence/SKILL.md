---
name: record-gate-evidence
description: >-
  Use at a crux dev-cycle / iterate quality-gates prompt (the dev module's "run
  quality gates" step) or the review module's gate re-run, or when the user says
  "record the gate", "capture the gate evidence", "run make check and log it",
  "what's the gate result", or "the run notes need the gate". Runs the repo's
  DECLARED merge bar (not a subset) and captures the canonical evidence line for
  the run notes — the exact command + the scope + the concrete result token — and
  flags when the gate actually run diverges from the declared bar. Closes the
  recurring failure where a cycle recorded gate evidence that diverged from the
  declared bar (a narrower scope, an omitted gate, or a number with no command).
metadata:
  tags: "quality-gate, dev-cycle, run-notes, fail-closed, evidence"
  bundles: "project-local"
  owner: "kitchen"
  version: "0.1.0"
  risk_level: "low"
  status: "production"
---

# record-gate-evidence

Run this at a cycle's quality-gates step (and the review module's gate re-run) to capture the gate
evidence the run notes need. Three consecutive cycles (PB-0011/13/14) recorded gate evidence that
diverged from the declared merge bar — a narrower scope (`src tests` instead of `make check`), an
omitted gate (format-check), or a bare number with no command. The run-snapshot reviewer
corroborates these tokens against the diff; an unrecorded or divergent gate reads as
fabrication-by-omission.

## The discipline

1. **Run the DECLARED bar, not a subset.** The declared merge bar is read from the repo's own
   source of truth — the root `Makefile`'s `check` target (the `check:` recipe lists the chained
   gates). Read it (`grep -A5 "^check:" Makefile`) and run EXACTLY that. If you run a subset for
   speed during iteration, that is fine for iteration — but the RECORDED gate evidence must be the
   full declared bar before you record it.
2. **Capture command + scope + result token, never a bare "green".** For each gate the bar chains,
   the record needs the exact command, the scope it ran over, and a concrete result token (a count,
   an `exit 0`, a "N passed"). The helper below produces this.
3. **Flag divergence.** If the gate you ran is NOT the declared bar (a subset, a missing gate, a
   different scope), the record must say so explicitly — name the gap — rather than record the wrong
   command as if it were the bar.

## The helper

`record_gate.py` runs a gate command (argv form) and emits the canonical evidence line: the command,
the working-directory scope, the exit code, and the result token parsed from the output. Run it from
the repo root:

```bash
uv run .claude/skills/record-gate-evidence/record_gate.py -- make check
```

It prints the canonical line to paste into the run snapshot's Notes, e.g.:

```
gate: `make check` (repo root) → exit 0 — pytest 2067 passed; ruff clean; mypy 63 files; bandit 0
```

The helper does not judge the bar; step 1 + 3 are the discipline. The helper guarantees the evidence
line is complete (command + scope + exit + token) so a bare "green" can't be recorded.

## Self-test (the closure criterion)

Run the helper against a fixture command with known output: `uv run .../record_gate.py -- python3 -c "print('3 passed')"`. PASS = the emitted line carries the exact command, the scope, `exit 0`,
and the `3 passed` token. The divergence check: run a command that is NOT the declared bar and
confirm the emitted line still names the ACTUAL command run (so the divergence is visible on the
line, not hidden).

## Red flags

- About to record a gate result without the command. The command is the evidence; a bare number is
  uncorroboratable.
- About to record a subset (a curated test selection) as if it were the declared bar. Run the bar;
  or record the subset AND name it a subset.
- About to paste raw command output that could embed a token/secret into the notes. Summarize; the
  helper emits the canonical line, not raw output.
