---
name: verify-test-teeth
description: "Use when authoring or reviewing any test, CI gate, counter-fixture, or eval harness in this repo — especially when a check is GREEN and you are about to trust it. Verifies the check can actually FAIL: that it exercises the real artifact (not a same-language re-implementation), that a completeness/quality backstop is not masking the defect it targets, that a defect-specific mutation turns it RED, and that its fixture is reachable. Catches the vacuous-green ('greenwash') failures that shipped in PB-0002 and PB-0003."
metadata:
  tags: "testing, review-discipline, teeth, verification, anti-greenwash"
  bundles: "crux-docs"
  owner: "crux"
  version: "0.1.0"
  risk_level: "low"
  status: "production"
---

# Verify Test Teeth

## Overview

A GREEN test proves nothing until you know it can go RED. This repo has
repeatedly shipped checks that passed not because the code was correct but
because the check **could not observe the defect it claimed to catch** — a
same-language re-implementation of the artifact, a fixture masked by a
downstream backstop, a gate that rewrote the file it validated, a
counter-fixture that was unreachable as worded. Each passed every green gate;
each was caught late, by review, only after someone asked "what makes this fail?"

This skill is that question, made into a checklist. Run it whenever you author
**or** review a test, CI gate, counter-fixture, or eval-harness case in this
repo — and specifically before you let a green result advance a change.

It is a **review discipline**, not a tool: it produces a verdict
(`teethed` / `vacuous`) and, for a vacuous check, the specific class and the
minimal change that gives it teeth. It never weakens shipped defenses (see the
backstop rule below).

## When to use

- Authoring a new test, CI gate, counter-fixture, or eval case.
- Reviewing someone else's test/gate/fixture in a diff.
- **A check is GREEN and you are about to rely on it** to advance a change,
  accept an ADR's acceptance criteria, or pass a quality gate — this is the
  highest-value trigger; a green result is exactly when vacuity hides.
- A reviewer says a test "looks fine" but nobody has shown it failing.

Do **not** use this for: general bug-finding in production code (that is
`code-review`), or for building the eval harness itself (this skill audits that
harness; it is not a substitute for it).

## The four vacuity classes

For the check under review, ask each question. Any "yes" (or "can't tell") is a
`vacuous` finding for that class.

### Class 1 — Re-implementation as oracle

**Does the test execute the REAL artifact, or a same-language re-implementation
of it?** A harness that reimplements the thing it checks certifies the
reimplementation, not the artifact. The reimplementation can be correct while
the real artifact is broken, and the test stays green.

- *Exemplar (PB-0002, `policy_harness.py`):* the AC-3 harness simulated the
  `SET LOCAL` setter in Python instead of executing the emitted DDL. Three
  DDL bugs that could never run against real Postgres passed every green gate,
  because the Python simulation was correct.
- *Teethed form:* the check runs the real emitted artifact (execute the DDL
  against a real engine), OR the simulation is explicitly named as a stand-in
  and the real-execution lane is a named, tracked graduation gate — never
  presented as if it verified the artifact.
- *Tell:* the test builds its own copy of the logic under test (re-derives the
  SQL, re-computes the score, re-parses the token) and asserts against that
  copy rather than driving the shipped code path.

### Class 2 — Backstop masking

**Is a completeness/quality backstop recovering what the defect would
otherwise expose?** Defense-in-depth is good in production and bad in a test:
a second mechanism that independently repairs the failure makes the test green
regardless of whether the component under test is broken.

- *Exemplar (PB-0003, `eval/teeth.py`):* the stock overfiltering counter-fixture
  passed end-to-end because the lexical full-scan leg (plus the structured leg)
  independently recovered the record a single vector-leg cap tried to hide. The
  counter-fixture had no teeth against the single-leg defect it targeted.
- *Teethed form:* write the teeth against the **backstop-absent** case from the
  start — disable or bypass the backstop **inside the test fixture only** so the
  targeted component's defect is observable (e.g. a fixture that caps every leg,
  or a backstop-disabled variant), and assert the suite goes RED on the defect.
- **Backstop rule (binding):** "disable the backstop" is a *teeth-authoring*
  posture — it lives in the test fixture. It is **NEVER** a directive to strip
  the backstop from the shipped/production check. The production defense-in-depth
  stays; the fixture reproduces the world without it.
- *Tell:* removing the component-under-test entirely (not just breaking it) still
  leaves the test green.

### Class 3 — Self-fulfilling / mutation-survives-green

**Does the check survive a mutation that targets the specific defect it claims
to catch?** If you can break exactly the thing the test is supposed to guard and
the test stays green, it has no teeth. A special case: a gate that **rewrites or
regenerates the very artifact it validates** always passes, because it
manufactures its own expected value.

- *Exemplar (PB-0003, `eval/config_gate.py`):* the config gate rewrote the
  attestation file it was supposed to validate, so even a junk committed
  attestation passed. De-tautologized into a gate path (validates the COMMITTED
  file, never rewrites → junk attestation goes RED) vs a separate regenerate path.
- *Teethed form:* the gate validates committed/external state it does not
  produce; and a mutation targeting the guarded defect flips it RED.
- **Mutation rule (binding):** the mutation MUST target the **specific defect the
  test claims to catch**, not a trivial unrelated change. A weak mutation
  (rename a variable, tweak whitespace) that flips the test proves nothing — it
  makes *this* skill's own check vacuous. State, in one line, which real defect
  the mutation reproduces before trusting the RED.
- *Tell:* the "expected" value is computed by the same code path that produces
  the "actual" value; or no one can name a one-line code change that would make
  the test fail.

### Class 4 — Unreachable fixture

**Is the fixture / counter-example actually reachable, or vacuously green as
worded?** A counter-fixture that can never trigger the condition it describes
passes for the wrong reason — the exact teeth-failure a counter-fixture exists
to prevent.

- *Exemplar (PB-0003, ADR-0003 drift-fixture direction-b):* a council-approved
  drift fixture was unreachable as worded, so it would pass vacuously; reworded
  to a reachable displacement form.
- *Teethed form:* prove the fixture's precondition is satisfiable and that the
  path it exercises is actually taken (e.g. by observing the intended branch
  execute, or by asserting the fixture fails when the guard is removed).
- *Tell:* the fixture's setup can't actually produce the state its assertion
  checks; the assertion is never evaluated against a live case.

## Procedure

1. **Name what the check claims to catch** — one sentence. If you can't, the
   check has no defined teeth; that is itself a `vacuous` finding.
2. **Walk the four classes** above. For each, answer the question against the
   real code (read the artifact under test AND the test; do not infer from
   names).
3. **Demand a RED** — for the strongest applicable class, produce (or describe
   precisely) the defect-specific mutation / backstop-absent fixture and confirm
   the check goes RED. A check nobody has seen fail is unproven.
4. **Verdict:**
   - `teethed` — executes the real artifact, no backstop masks the target, a
     defect-specific mutation goes RED, fixture reachable.
   - `vacuous` — name the class(es), and give the minimal change that adds teeth
     (per the teethed-form line for that class).
5. Report the verdict and, for `vacuous`, the class + fix. Do not silently pass
   a green check you could not make fail.

## Red flags — STOP

- **About to trust a green check because "it passes."** Passing is the state
  this skill exists to distrust. Show it failing first.
- **About to strip a backstop from the shipped check** to make a test bite.
  Never — the fixture reproduces the backstop-absent world; production keeps its
  defense-in-depth (Class 2 backstop rule).
- **About to accept a mutation that flips the test but doesn't reproduce the
  guarded defect.** A trivial mutation proves nothing (Class 3 mutation rule).
- **About to assert against a value your own test computed the same way the
  artifact does.** That is a re-implementation oracle (Class 1) or a
  self-fulfilling gate (Class 3).

## Rationalization table

| Excuse | Reality |
|--------|---------|
| "It's green and the CI is happy — ship it." | Green is when vacuity hides. A check that has never been shown to fail is unproven. |
| "Simulating the artifact in Python is easier and equivalent." | It certifies the simulation, not the artifact (PB-0002: three unrunnable-DDL bugs passed a correct simulation). Execute the real artifact or name the stand-in explicitly. |
| "Defense-in-depth means the pipeline is robust — the test passing is fine." | The backstop makes the test green regardless of the component under test. Write teeth against the backstop-absent case; keep the backstop in production. |
| "I broke something and the test went red, so it has teeth." | Only if what you broke is the specific defect the test claims to catch. A trivial mutation flipping it proves nothing. |
| "The gate validates the file, and it passes." | If the gate rewrote the file first, it validated its own output. Validate committed/external state; confirm a junk input goes red. |
| "The counter-fixture is approved, so it must bite." | Approval isn't reachability. A fixture unreachable as worded passes vacuously — prove its precondition is satisfiable. |
