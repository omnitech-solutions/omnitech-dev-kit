# SCALING — from one feature on one repo to many, without losing the discipline

The pilot ran one unit at a time, one feature, one repo, one harness, one human. That is the correct default
while the false-green rate is high. This file says what changes, and what must not, as each axis grows.

## What never changes (the five invariants)
1. A unit is a packet with an **exclusive** owned-file set, executed in its **own worktree**.
2. The **verifier is a different run** from the worker and re-runs the declared bar itself.
3. The definition of done carries **counts**, and names a **live-boundary gate a model does not run**.
4. Every paid run has a **wall clock, a tool boundary, no session, and a spend row**; guards are stops.
5. Artefacts are **validated by shape** (packet, receipt, evidence, ledger, spend) before a human reads them.

If a scaling step would break one of these, it is not a scaling step.

## Axis 1 — more units in flight (parallelism)
- Two units may run concurrently when their packets' §2 sets are **disjoint** and neither touches a shared
  protected input. The orchestrator can be asked to state disjointness explicitly; the human checks it.
- One worktree per unit (`../wt-<unit>`), one spend row per run, one campaign folder. Nothing else is needed.
- **Never** run a live-boundary measurement or a human re-capture while any verifier or e2e run is executing on
  the same machine (lesson: a phantom performance defect). Queue them.
- The ceiling is human review: one reviewer closes ~one unit per 25–40 min. Parallel model runs beyond ~2–3 per
  reviewer only build a queue of unreviewed receipts, and an unreviewed ACCEPT is worth nothing.
- Fleet tools (Conductor, Composio orchestrator, Claude Squad, Gastown) manage many sessions; they do not supply
  packets, receipts or verification. Adopt one only when the queue above is the bottleneck, and keep `run.py` as
  the thing each session actually executes.

## Axis 2 — more features in one repo
- One campaign folder per feature: `<owner>/kit/<feature>/` with its own AGENTS file, ledger, fixtures, packets,
  receipts, spend. `init_project.py` scaffolds it in two minutes.
- The AGENTS file is copied from the last feature and three things change: mission, owned directories, gates
  baseline. Everything else is repo law and should be identical; if it is not, one of them is wrong.
- One `spend.jsonl` per campaign; the `campaign` field in each row (`<repo>/<feature>`) lets a one-line
  `jq` sum across campaigns. Caps are per campaign; the key usage baseline is taken at each campaign start.
- Shared gates (typecheck, unit bar, structural scan) are the repo's; a feature adds its own live gate.

## Axis 3 — more projects
- One kit, many consumers. Projects keep only their own material (README "What a consuming project keeps").
  The kit keeps shapes, promptbooks, adapters, lessons and the single forge log.
- Lessons and forge-log entries are written in project-neutral words and name the project only in the body.
  After two projects, `crux retrospective` (or a human reading `lessons/`) can see which disciplines repeat.
- Do not fork the kit per project. A project that needs a different promptbook has found either a bug in the
  promptbook (fix it in the kit) or a project rule (put it in that project's AGENTS file).
- Version the kit (`plugin.json`), and let a project pin a tag when a campaign is mid-flight.

## Axis 4 — more harnesses and models
- The contract is `run.py` + `harness/<name>.sh`. HARNESSES.md is the matrix; each row says what the harness
  cannot express (Codex: no tool list, sandbox instead; OpenCode: agent file instead; Claude: Anthropic models only).
- Model choice is per role in `kit.config.json`, never in a prompt. Rule of thumb: the cheapest model that has a
  bar to check it; one tier up only for the planner; a frontier model never inside the loop.
- Local models (OpenCode + LM Studio/Ollama) drop cost to zero and make the wall clock the only guard; set
  `usage_probe: none`, and expect longer `max_time`.
- Mixed harnesses in one campaign are fine (e.g. Codex implementer, OMP verifier): the receipts are files.

## Axis 5 — more people
- The human gates are roles, not a person: **packet reviewer**, **live-gate runner**, **committer**. One person
  can hold all three; two people should split reviewer from committer.
- Everything a second person needs is in the campaign folder and the kit; if a decision lives only in chat, write
  it into the packet (§8 out of scope is usually where it belongs) or the RUNBOOK.
- A team that already runs crux gets ADRs, council and retrospective from crux; the kit stays underneath as the
  execution layer (COMPAT.md). A team without crux runs the kit alone and writes decisions into the campaign
  `OBJECTIVE.md`.

## What to measure to know it is scaling
| Signal | Healthy | Act when |
| --- | --- | --- |
| cost per committed unit | $0.05–0.12 (Flash-class) | > $0.20: find the timeouts in spend.jsonl |
| model-verdict false-green rate | falling toward 1 in 5 | not falling: the live gate is weak or the AGENTS invariants are vague |
| timeouts per 10 runs | ≤ 1 | ≥ 3: reader/planner prompts are too wide |
| human minutes per unit | 20–30 | > 45: packets need more §3 detail or rows are too big |
| REJECT rate | 10–30% | 0%: the verifier is rubber-stamping; > 50%: packets are wrong before execution |

## The order to grow in
Parallel units (axis 1) only after ten serial units on the same repo with a false-green rate under one in three.
Second feature (axis 2) as soon as the first ledger is closed. Second project (axis 3) after two features.
Second harness (axis 4) when a project or person requires it, never for its own sake. More people (axis 5) once
the packets are good enough that a reviewer who did not write the evidence note can still approve one.
