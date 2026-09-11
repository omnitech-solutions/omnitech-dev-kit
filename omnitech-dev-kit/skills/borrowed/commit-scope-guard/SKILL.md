---
name: commit-scope-guard
description: "Use at a cycle's PREP/commit step, before committing — 'check the commit scope', 'is my working tree clean of unrelated changes', 'what unrelated files would this commit sweep in', 'guard the commit scope', 'flag out-of-scope staged files'. Given the cycle's intended file set, diffs it against git status (staged AND unstaged) and reports every changed path outside that set as a candidate for exclusion. Read-only and advisory — it never stages, restores, or resets anything; you decide what to exclude."
metadata:
  tags: "git, commit-hygiene, cycle-prep, scope, review"
  owner: "mark"
  version: "0.1.0"
  risk_level: "low"
  status: "production"
---

# commit-scope-guard

## Why this exists

Recent cycles repeatedly ended needing a manual carve-out of **unrelated
pre-existing changes** from the commit — the author commits by hand and has been
handed an exclusion list each time:
- PB-0007 flagged pre-existing `USER_GUIDE.md` / `.gitignore` edits and staged
  `docs/reviews`, `docs/codebase` as "out-of-cycle, not defects."
- PB-0009 had to explicitly exclude `LODESTAR_USER_GUIDE.md` + `docs/codebase/*`
  from the commit as "unrelated scope-creep."

Both landed the same trap: a dirty working tree carrying changes from outside the
cycle's scope, discovered at commit time and reconciled by hand. This skill makes
that check mechanical so scope-creep is surfaced before — not during — the commit.

## When to use

Run it at the cycle's **prep / commit prompt**, just before staging or committing.
Pass the cycle's intended touched-file set — the paths the run snapshot's
`artifacts` / the dev module's scope say this change should touch.

## How to run

```bash
python3 .claude/skills/commit-scope-guard/guard.py <intended-path-or-prefix> [<more...>]
```

Each argument is an exact repo-relative path **or** a directory prefix (everything
under it is in scope). Example:

```bash
python3 .claude/skills/commit-scope-guard/guard.py \
  packages/foundation/src/syscall proto/legion/syscall corpus/syscall .lodestar/docs
```

## Output

Two lists — `IN-SCOPE` and `OUT-OF-SCOPE` — over every changed path (staged and
unstaged), then a verdict:

```
OUT-OF-SCOPE (2) — review before committing:
  [ M] LODESTAR_USER_GUIDE.md
  [A ] docs/codebase/foo.md  (staged — `git restore --staged` to drop it)

VERDICT: 2 out-of-scope change(s) — decide per file whether to exclude ...
```

Staged out-of-scope files carry a `git restore --staged` hint **for you to run** —
the skill prints the suggestion but never executes it.

## Read-only contract (important)

This skill is **strictly advisory**. It runs `git status` only. It NEVER stages,
restores, resets, cleans, or commits — nothing in your tree or index changes when
you run it. It always exits 0 (it is a review aid, not an acting gate). Every
exclusion decision is yours; act on the review list by hand.

## Limitations

- Scope matching is by exact path or directory prefix. It does not glob (`*.md`);
  pass the directory prefix instead.
- It reports the change status code from `git status --porcelain` but does not judge
  *why* a file changed — a legitimately-in-scope file you forgot to list will show as
  out-of-scope. Curate the intended set from the run snapshot's artifacts.
- Renames report the destination path only.
