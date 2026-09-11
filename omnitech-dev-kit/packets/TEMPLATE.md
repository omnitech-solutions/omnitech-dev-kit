# Packet <UNIT-ID> — <one-line title>

Status: DRAFT (orchestrator) → REVIEWED (human) → EXECUTED → VERIFIED
Ledger row: <id>. Fixtures: <oracle path>, <subject path>.
Gap in one sentence: <...>

## 1. Protected inputs (in addition to the AGENTS file)
- <paths the implementer must not touch, including tests not named below>

## 2. Owned files (EXCLUSIVE — the implementer edits nothing else)
- <path> — <what changes>
- <test path> — <cases added>

## 3. Todo DAG (each ≤ ~80 LOC, independently checkable)
1. <step> → touches <file>

## 4. Structural evidence required before claiming
- <AST query> — expected: <...>

## 5. Real-boundary test
- <which existing test file gains which case; what it asserts against the real artifact>

## 6. Definition of done (fail-closed, with counts)
- <gate> ≥ <baseline> and every new case in §5 present and green; <other gates>.
- Human re-capture of the subject fixture shows the oracle behaviour.

## 7. Checkpoint / resume predicate
- If time runs out: write `receipts/<UNIT>-execution.md` with the completed DAG steps and the
  failing command's output. Resume = re-run from the first unchecked step.

## 8. Out of scope (explicit)
- <at least three tempting additions>
