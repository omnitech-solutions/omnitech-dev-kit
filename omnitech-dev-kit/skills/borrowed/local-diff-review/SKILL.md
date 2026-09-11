---
name: local-diff-review
description: >-
  Use when the user says "review my local changes", "review the working tree",
  "review this diff", "review my diff", "code-review without a PR", "review
  HEAD~1..HEAD", "review the staged changes", "local diff review", or when a
  crux dev-cycle / iterate internal-review prompt (Prompt 8) needs a structured
  code-review but there is NO GitHub PR to target. The local-working-tree
  analog of the PR-based `code-review`/`review` skill: it reviews a local git
  diff directly. Read-only — no PR, no `gh`, no network, no git mutation.
metadata:
  tags: "code-review, local-diff, git, fail-closed, quality-gate"
  bundles: "project-local"
  owner: "kitchen"
  version: "0.1.0"
  risk_level: "low"
  status: "production"
---

# local-diff-review

## Overview

Run a structured code-review over a **local git diff** — a ref range, staged
changes, or the working tree — and emit ranked findings. This is the
local-working-tree counterpart to the installed `code-review`/`review` skill,
which requires a GitHub PR (`gh pr view` / `gh pr diff`). crux dev-cycles and
`iterate` runs develop locally with no PR, so their internal-review prompt has
nothing for the PR-based skill to target and has been falling back to ad-hoc
manual review. This skill closes that gap.

**Read-only contract (binding).** This skill NEVER mutates state. It runs only
`git diff` / `git show` / `git log` / `git rev-parse` and reads files. It does
NOT stage, commit, push, open/merge a PR, invoke `gh`, or make any network
call. If a step seems to require any of those, stop — it is out of scope for
this skill.

## When to use

- A crux dev-cycle / `iterate` internal-review prompt with no PR (local
  working-tree development).
- The user asks to review uncommitted or unpushed changes before committing.
- Any time you want the crux review rubric applied to a diff that is not (yet)
  a pull request.

**When NOT to use:** there is a real GitHub PR — use the installed
`code-review`/`review` skill instead (it carries PR context and can post
review comments). This skill is for the no-PR case only.

## Inputs

- **Diff source** (optional). Resolve in this priority order:
  1. An explicit range or ref the caller names — `<refA>..<refB>`, a single
     `<ref>` (diff that ref against the working tree), or a branch/merge-base
     (e.g. `main...HEAD`). → `git diff <range>`.
  2. `--staged` / "staged changes" → `git diff --cached`.
  3. **Default** (no source named): the full working-tree delta →
     `git diff HEAD`. If the repo has no commits yet, fall back to `git diff`.
- **Scope hint** (optional): a path or subtree to restrict the review to
  (append `-- <path>` to the git command).

## Procedure

### 1. Resolve and capture the diff (read-only)

Confirm you are in a git repo: `git rev-parse --is-inside-work-tree`. Then
capture the unified diff for the resolved source, e.g.:

```
git diff <range>                # explicit range
git diff --cached               # staged
git diff HEAD                   # default: working tree vs HEAD
git diff HEAD -- <path>         # scoped
```

Use `--stat` first to see the shape (files + churn), then the full `git diff`
(optionally `-U10` for more context) for the hunks. For a committed range you
may also `git show <ref>` a specific commit. **Only these read-only git
commands and file reads are permitted.** Never `gh`, `curl`, `http(s)`, or any
network fetch; never a git command that writes (`add`, `commit`, `push`,
`checkout -b`, `stash`, `reset`, `rebase`, `merge`).

If the diff is empty, report "no changes in the resolved diff source" and stop.

### 2. Read enough surrounding context

A diff hunk alone hides callers, invariants, and the ADRs a change must honor.
For each non-trivial hunk, read the surrounding function/module and any
directly-related file (the test that should have changed, the ADR whose
invariant the code claims). Cite the ADR/spec by path when a finding turns on
it. Do not review a hunk you do not understand — read until you do.

### 3. Apply the review dimensions

Review every changed hunk against these dimensions (the crux rubric):

- **Correctness / logic** — off-by-one, wrong operator, mishandled `None`/empty,
  broken control flow, incorrect error propagation, resource leaks.
- **Security & fail-closed posture** — the load-bearing dimension for this
  project. Flag in particular:
  - **fail-open `assert` guards**: an `assert` used as a security/validation
    gate is stripped under `python -O`, so the guard silently vanishes in
    production. A guard that must hold MUST `raise`, never `assert`.
  - **gate-verifies-one-object-but-acts-on-another**: code that checks object A
    then executes/persists object B (the two must be the same object).
  - injection, unsanitized input, secrets in code/logs, over-broad exception
    handlers that swallow refusals, missing tenant/authorization scoping.
- **Test coverage of the diff** — does the change ship tests that exercise the
  new/changed behavior, including negative and boundary cases? A behavior
  change with no test is a finding.
- **ADR / invariant conformance** — does the code actually enforce the
  invariant it (or its ADR) claims? Name the ADR and the invariant.
- **Simplification** — dead code, needless complexity, duplication a small
  refactor removes. (Lowest priority; never let it crowd out the above.)

### 4. Emit findings — ranked, structured, most-severe first

Output a ranked list (HIGH → LOW). Each finding:

- **severity**: HIGH | MEDIUM | LOW
- **location**: `path:line` (the line in the post-change file; anchor to the
  diff hunk)
- **category**: correctness | security | fail-closed | test-coverage |
  adr-conformance | simplification
- **defect**: one sentence — what is wrong.
- **failure scenario**: concrete input/state → wrong output/crash/vuln.
- **suggested fix**: the minimal change that closes it.

End with a one-line verdict: **SHIP** (no HIGH, no unaddressed MEDIUM),
**SHIP-WITH-FIXES** (fixable MEDIUMs named), or **BLOCK** (≥1 HIGH). If a
`ReportFindings` tool is available in the session and the caller is a
review-reporting context, you may report through it instead of prose — the
fields above map directly onto it.

If there are genuinely no findings, say so plainly ("no findings in N changed
files") — do not manufacture nits to look thorough.

## Verification checklist

- [ ] Ran only read-only git commands + file reads; no `gh`, no network, no
      git write.
- [ ] Resolved the diff source by the priority order (explicit → staged →
      working tree).
- [ ] Read surrounding context for every non-trivial hunk before judging it.
- [ ] Applied all five dimensions; checked explicitly for fail-open `assert`
      guards and gate/act object mismatches.
- [ ] Findings are ranked most-severe-first with `path:line` anchors and a
      failure scenario each.
- [ ] Ended with a SHIP / SHIP-WITH-FIXES / BLOCK verdict.

## Red flags — STOP

- About to run `gh`, `curl`, or any network fetch → out of scope; this skill is
  local-only. If the user wants a PR review, use the PR-based `code-review`
  skill instead.
- About to `git add` / `commit` / `push` / `checkout` / `stash` → this skill is
  read-only. Review only; let the human act on the findings.
- About to review a hunk you don't understand from the diff alone → read the
  surrounding code and the relevant ADR first.
- About to pass over an `assert` in a validation/security path → that is the
  signature failure mode this project cares about; flag it.
