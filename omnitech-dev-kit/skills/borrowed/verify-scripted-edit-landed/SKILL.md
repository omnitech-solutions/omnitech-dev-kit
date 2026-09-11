---
name: verify-scripted-edit-landed
description: "Post-edit verification guard for SCRIPTED text-replace mutations (python str.replace / sed / heredoc refactors / mechanical multi-site folds). Run right after any scripted edit — before claiming 'fixed' or 'folded' — to catch the recurring silent-edit class: a replace whose old text didn't match (silent no-op), a heredoc/quoting slip that corrupts structured files (the unterminated-scalar case), and a multi-site fold applied to prose but not to the binding site (the AC-bullet miss). Trigger phrases: 'verify the edit landed', 'did that replace actually apply', 'check my scripted edit', 'silent no-op replace check', 'did the fold cover every site', 're-validate after mutation', 'confirm the edit didn't no-op'. Invoke it manually, pointed at ONE scripted edit (the list of intended replacements) and the target file(s). It greps and parses; it does NOT re-run the edit. Distinct from ground-adr-substrate-claims (which verifies an ADR's factual claims against source) and confirm-fix-covers-production-path (which audits a test's call path) — this skill verifies that a scripted mutation physically landed, completely and without corruption."
metadata:
  tags: "edit-verification, scripted-edits, false-green, yaml, fail-closed"
  bundles: "crux-docs"
  owner: "project-local"
  version: "0.1.0"
  risk_level: "low"
  status: "production"
---

# Verify Scripted Edit Landed

A mandatory post-edit guard. Scripted replaces (`str.replace`, `sed`, heredoc refactor
scripts) fail **silently**: a zero-match replace is a no-op with exit code 0, and a
quoting slip writes corruption that looks plausible at a glance. Three incidents across
PB-0013/PB-0014 shipped a false "fixed" claim this way — each caught by a reviewer, never
proactively. This guard is the proactive half.

**Invoke it on every scripted edit, however small.** The edit tool's exact-match failure
mode is loud; the scripted-replace failure mode is silent. If you scripted it, you verify it.

## The four checks (apply in order)

### 1. Pre-replace match reality (no silent no-op)

For every intended replacement: the OLD text must have matched **at least once** before
the edit. If you still have the script/diff: re-grep the OLD text against the pre-edit
state (`git show HEAD:<file>` or the backup). Zero matches = the replace no-op'd —
**CONFIRMED**. (If you already ran the replace: check that the pre-edit count of OLD
minus the post-edit count of OLD equals the number of intended sites.)

### 2. Scoped presence of the new text (site-scoped, NOT global-elimination)

The NEW text greps live **at every intended site** — and only this. Do NOT demand the old
text vanish everywhere: legitimate other occurrences of similar text may exist (the
over-matching-guard failure mode — a naive "old text must be gone" check false-flags real
content). Verify presence at the intended sites; verify absence of the old text **at
those sites**, not globally.

### 3. Structured-file re-validation

After ANY mutation to a structured file (YAML, JSON, TOML, schema documents): re-parse
it. A YAML run snapshot must still validate (`yaml.safe_load` + the project validator,
e.g. `validate-promptbook.py --kind run` for run snapshots); a JSON file must parse. A
broken parse = **CONFIRMED** — the classic case is a heredoc/quote slip producing an
unterminated scalar that no reviewer reads closely enough to spot. **Never advance a
structured-file mutation without re-validating in the same step.**

### 4. Blast-radius for multi-site folds

When one concept must change in several places (a renamed column, a folded council fix, a
contract update): grep the concept's blast radius — EVERY site it binds (all text
occurrences, the binding AC/checklist/enumeration sites, the index rows, the comment
references) — not just the section you edited. The PB-0014 miss: a six-column correction
applied to the Decision text but not the binding AC bullet. Check 4 is what catches it;
checks 1–3 do not.

## Worked examples (from live incidents)

- **The silent no-op "fix" (PB-0013):** `str.replace(old, new)` where `old` didn't match
  → exit 0, file unchanged, snapshot recorded "fixed". Check 1 flags it: zero pre-edit
  matches for `old`.
- **The heredoc quote-consume (PB-0014):** a replacement string ended `...00Z'''` — the
  closing `'` was the heredoc delimiter, so five `started:` scalars landed unterminated
  and four later done-replaces then no-op'd on the malformed text. Check 3 flags it
  (YAML ScannerError on re-validation); check 1 flags the four no-op'd done-replaces.
- **The AC-bullet fold miss (PB-0014 R2):** check 4 — grepping "six" across the ADR shows
  the Decision section corrected but the AC bullet still saying "five".

## Red flags — STOP and reconsider

- **About to claim "fixed" after a scripted edit without running checks 1–3.** This is
  the whole skill. An unverified "fixed" is a false-green waiting for a reviewer.
- **About to demand the old text vanish globally (check 2).** Site-scoped, not global.
  Over-matching this guard creates the false-positive class the skill exists to avoid.
- **About to skip re-validation because the edit was "only one line".** The unterminated-
  scalar case WAS one line, five times. Re-validate every structured-file mutation.
- **About to treat the edit tool's success message as verification.** It verifies the
  tool ran, not that the intent landed. Grep the intent.

## Rationalization table

| Excuse | Reality |
|---|---|
| "The replace obviously matched — the file looks right." | The three incidents all "looked right". Plausible-looking corruption is exactly what quoting slips produce. Grep, don't glance. |
| "Re-validating YAML after every edit is overkill." | A YAML parse is milliseconds. A broken snapshot costs a conformance reviewer + a repair cycle. This is the cheapest check in the guard. |
| "The fold only touched one section — no blast radius to check." | The AC-bullet miss was also "one section". If the concept binds anywhere else, it has a blast radius. Grep first, conclude second. |
