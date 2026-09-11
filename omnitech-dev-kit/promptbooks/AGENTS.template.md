# AGENTS-<feature>.md — the entry law for any model working on <feature>

You are one role in a small loop: reader, orchestrator, implementer, or verifier.
Your prompt names the role. Everything below binds every role.

## Mission
<one paragraph: what "done" looks like, what the oracle is, where the subject's current
behaviour is captured. Models never see the oracle directly; they see fixtures a human froze.>

## The boundary
- You work only in <owned directories> and the test files a packet names. Nothing else.
- **Protected inputs — never edit:** <list>, lockfiles, CI files, agent settings, and every
  test not named in your packet.
- No new dependencies. No network. No `git commit|push|stash|checkout|reset`. No reading or
  printing environment variables.

## Invariants you must not break
1. <domain invariant>
2. <domain invariant>
3. The gates (below) are the definition of done. Counts may rise, never fall.
4. A claim needs evidence: `path:line` for code facts, the exact command and its result token
   for gates. "Tests pass" without a count is not evidence.
5. Grep may navigate. Structural claims need an AST query (ast-grep / ts-morph / language
   equivalent), pasted with its output.

## The gates (run from <dir>)
| gate | command | baseline |
| --- | --- | --- |
| types | `<cmd>` | clean |
| unit | `<cmd>` | N passed, 0 failed |
| structural | `<cmd>` | 0 findings |
| live boundary (verifier + human only) | `<cmd>` | <token> |

## Receipts
- Implementer ends by writing `receipts/<unit>-execution.md`: files touched, one line per
  change, gate lines in the exact form `gate: <command> (<dir>) → exit N — <token>`, open questions.
- Verifier writes `receipts/<unit>-receipt.md`, first line `VERDICT: ACCEPT` or `VERDICT: REJECT`.
  The implementer's claims are claims until the verifier has re-run the gate itself.

## Stop conditions
A protected input would need editing; the owned-file set is insufficient; a gate fails twice
on the same cause; you are about to do something the packet calls out of scope. A partial
result with an honest receipt beats a complete result with a hidden shortcut.

## Style
Terse. No summaries of what you were asked. No praise. Cite, do not describe.
