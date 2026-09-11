# Forge log

_Written by forge-skill. Entries newest-first. Events: authored | revised | used | evaluated | fallback | escalated | pruned. forge-skill is the sole writer of the lifecycle events (authored, revised, pruned); the usage events (used, evaluated, fallback, escalated) are written by the session that used the forged skill, in forge-skill's locked format._

_Kit note: this single log serves every project that installs omnitech-dev-kit. Entries name the project in the body line, never in the header. Format is crux's, verbatim; `kit-check-crux-compat` fails if upstream changes it._

## [2026-09-10 19:15] evaluated | verify-test-teeth
- verdict: effective | gap: closed | recommend: keep
- evidence: legion-os-surveys FF-04 — verifier's own mutation run turned the new test RED on the guarded defect; class 1–4 all satisfied; the receipt cites the binding line

## [2026-09-10 19:15] evaluated | verify-test-teeth
- verdict: mixed | gap: partial | recommend: keep
- evidence: legion-os-surveys FF-01-R1 — teeth held at the unit level (651 green, mutation RED) but the ACCEPT was wrong at the live boundary; the skill cannot see StrictMode remounts, the live gate can

## [2026-09-10 19:15] evaluated | record-gate-evidence
- verdict: effective | gap: closed | recommend: keep
- evidence: legion-os-surveys FF-09 — implementer's gate lines claimed typecheck clean on a non-compiling file; the verifier's re-run in the exact gate form exposed the false claim

## [2026-09-10 19:15] evaluated | commit-scope-guard
- verdict: fell-short | gap: not-closed | recommend: revise
- evidence: legion-os-surveys FF-09 — the worktree diff was in scope while the implementer had also edited the MAIN checkout via absolute paths; the guard sees one tree, the leak was in another (lesson filed: worktree-relative paths only)

## [2026-09-10 19:15] used | local-diff-review
- legion-os-surveys FF-06: declaration-by-declaration CSS audit against the packet §3.2 spec, verifier receipt — ok

## [2026-09-10 19:15] used | verify-scripted-edit-landed
- legion-os-surveys FF-09: hand recovery after a scripted edit left a duplicated block on disk; re-read before re-run — ok

## [2026-09-10 19:15] fallback | verify-test-teeth
- legion-os-surveys FF-04 e2e extension: the borrowed skill targets unit tests; the model-written live check had no teeth (green before and after); human ran it against the unfixed tree instead — partial
