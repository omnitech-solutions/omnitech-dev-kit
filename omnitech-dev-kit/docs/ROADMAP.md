# Roadmap — what the hardening pass deliberately did not build

Date: 2026-09-10. The v0.2.x hardening pass made the existing path truthful: admission before spending,
boundaries that refuse when they cannot be enforced, records that survive failure, validators that catch
self-contradiction. That is the floor, not the design. Four structural pieces are still missing, in the
order they are worth building.

## 1. A machine-checked unit lifecycle
Today a model writes `VERDICT: ACCEPT` in Markdown and a human decides what it means. There is no state a
tool can refuse to advance.

```
EVIDENCED → PACKET_REVIEWED → IMPLEMENTED → VERIFIED → LIVE_ACCEPTED → APPLIED
                    plus BLOCKED, REJECTED, SUPERSEDED
```

The runner should own the legal transitions, and each transition should reference immutable identities:
packet revision, resolved policy digest, fixture identity, base revision, candidate content digest, gate
executions, human approval. The invariant to enforce is **evidence authorises only the candidate and the
conditions it actually examined** — change the packet, the policy, the fixtures or the candidate and any
dependent acceptance is void. This closes the "verified one thing, applied another" failure class, which
the current apply recipe only mitigates by staging the worktree first.

## 2. A trusted gate runner
Gate lines are still prose a model wrote, re-run by another model. The kit should execute the declared
gates itself and record command, working directory, exit code, output reference, environment identity and
candidate digest. The model may explain a failure; it should not be the author of the authoritative record.
Verifier isolation belongs here too: the candidate source read-only, caches and build output writable
elsewhere, mutation testing on a disposable copy so mutations can never reach the accepted candidate.

Related: stop treating a test count as the contract. A count survives deleting a valuable case and adding
several trivial ones. Bind required behaviour to identifiable cases.

## 3. Composable policy instead of copied law
`docs/SCALING.md` currently says to copy the previous feature's AGENTS file and change three sections. That
guarantees divergence. Resolve policy through four layers instead — kit safety contract, project policy,
feature policy, unit packet — and generate the AGENTS file and RUNBOOK as marked derived artefacts that
record where each effective rule came from.

The merge rule is the important part, and it is not last-write-wins: **permissions intersect, mandatory
checks accumulate, denials win, budgets become no less restrictive, conflicts stop resolution.** A feature
must not be able to drop a repository gate by supplying its own list.

This also needs a separation the kit does not yet make: a **safety invariant** ("no writes outside the
approved scope") is not the same as an **operating heuristic** ("reader questions name at most five files").
The heuristics in `lessons/` and `COST-MODEL.md` come from one feature on one codebase. Treat them as
versioned profile defaults with an applicability note, not permanent law. A lesson is evidence for a
proposed rule; it is not automatically an invariant.

## 4. A real bridge to crux
The kit writes `forge-log.md` in crux's locked format, in the kit repo. Crux's retrospective reads a
different location. Matching a format is not being discoverable. Build and test the bridge end to end: one
kit incident reaching the intended crux surface, with stable identity and no double counting. Until then,
describe the kit's log as the kit's own evidence, not as retrospective input.

Also: authoritative cross-project history should not live inside a versioned plugin installation. Keep the
evidence in durable project or configured shared storage and make the global view an aggregation of it.

## What self-correction should and should not do

Split it in two.

**Mechanical correction, safe to automate inside approved boundaries:** regenerate a derived AGENTS
projection from already-approved policy, rebuild an index, block a stale receipt, reconcile an interrupted
run record. Even here, report a conflict rather than overwrite a file that carries unapproved local edits.

**Semantic learning, always a reviewable proposal:** incident → reproducible case → scoped proposal →
review → approved revision → replay → controlled activation. Start every proposal at the smallest valid
scope: an observation from one feature is a rule candidate for that feature. "Seen twice" is evidence of
recurrence, not proof it belongs everywhere. Evaluate a proposed rule against both the historical failure
and nearby legitimate work, so its false-positive cost is known before it is switched on.

Automatic correction must never change the oracle, lower a required gate, widen writable scope, raise a
budget ceiling, or accept its own candidate.

## Measurement worth trusting
Prefer cost per **live-accepted, applied** unit; human rework minutes; false ACCEPTs among units with known
live outcomes; runs with missing evidence; unmetered runs; repeated failure causes; proposed-rule false
positives. Treat the pilot's rates in `SCALING.md` as observations from a ten-unit sample on one feature,
not as operating targets. A zero rejection rate is a prompt to look, not proof of rubber-stamping.

## The strongest next test
Point `verify-test-teeth` at the kit itself: remove a boundary, feed it a stale or self-contradictory
receipt, omit a gate, corrupt a config, and confirm the control layer refuses to advance. The hardening
pass did a first pass of exactly this by hand; it belongs in a suite.
