# omnitech-dev-kit

A **companion plugin to [crux](https://github.com/bionic-coding/crux)**. crux owns project memory
(the `bionic/` tree, ADRs, promptbooks, council, forge-skill, retrospective). This kit adds the
execution discipline that sits underneath a unit of work and is not project-specific:

- **Packets** — one bounded, exclusive-scope execution spec per unit (`packets/TEMPLATE.md`, `schemas/packet.schema.json`).
- **Receipts** — the worker writes a *claim*; an independent verifier re-runs the declared bar and writes a *receipt* whose first line is `VERDICT: ACCEPT|REJECT`.
- **Cost-guarded runs** — `scripts/run.py` starts one role run under a wall-clock cap, a tool allow-list, no session, a per-run and per-campaign dollar guard, and a spend row.
- **Harness adapters** — `harness/omp.sh`, `harness/claude.sh`: the promptbooks never change when the harness does.
- **One forge log for all projects** — `forge-log.md` in crux's locked seven-event format, so evidence about which skills pay off accumulates across repos instead of per repo.
- **Borrowed disciplines** — Mark Madsen's forged review skills, copied with provenance (`skills/borrowed/`).

crux is **not vendored here**. Install crux from its own marketplace, then install this kit beside it.
`COMPAT.md` is the contract that keeps this kit working across crux releases; `kit-check-crux-compat`
enforces it.

## Install

```
/plugin marketplace add bionic-coding/crux
/plugin install crux@crux
/plugin marketplace add <path-or-github>/omnitech-dev-kit
/plugin install omnitech-dev-kit@omnitech-dev-kit
```

For OMP (which loads `~/.omp/agent/skills/` rather than plugins) run `scripts/sync_skills.py` — it
mirrors `omnitech-dev-kit/skills/**` into that directory and prints a receipt.

## What to say

| Say | The kit will |
| --- | --- |
| "write a packet for `<ledger row>`" | run the orchestrator promptbook: one packet in the template shape, no code edits |
| "run unit `<id>` as `<role>`" | start one cost-guarded role run through the chosen harness adapter |
| "verify `<unit>`" | run the verifier promptbook over the worker's claim in its worktree and write the receipt |
| "record evaluation for `<skill>`" | append one `used` or `evaluated` entry to `forge-log.md` in crux's locked format |
| "sync skills" | mirror kit skills into the machine-local live skill directories, with a receipt |
| "check crux compat" | verify the installed crux version, skill-name collisions, and forge-log format drift |

## Layout

```
.claude-plugin/marketplace.json     marketplace pointing at ./omnitech-dev-kit
omnitech-dev-kit/                   the plugin
  plugin.json, .claude-plugin/plugin.json
  skills/kit-*/SKILL.md             kit skills (all names prefixed kit- to avoid crux collisions)
  skills/borrowed/                  Mark's forged skills + PROVENANCE.md
  promptbooks/                      role prompts: read, orchestrate, implement, verify
  packets/TEMPLATE.md               the packet shape
  schemas/*.schema.json             packet, receipt, ledger-row, spend
  scripts/*.py                      stdlib-only: run, validate, check_crux_compat, sync_skills
  harness/*.sh                      omp, claude adapters
forge-log.md                        cross-project forge log (crux locked format)
lessons/                            one dated file per hard-won lesson, project-neutral wording
objectives.md                       what this kit is for; the ruler for every proposal
inbox/                              drop zone; crux's "process inbox" files items
COMPAT.md                           the crux compatibility contract
kit.config.example.json             caps, key source, harness defaults
```

## What a consuming project keeps

Only its own: `AGENTS-<feature>.md` (from `promptbooks/AGENTS.template.md`), `ledger.md`,
`fixtures/`, `packets/`, `evidence/`, `receipts/`, `runs/`, `spend.md`, and an `OBJECTIVE.md`.
Nothing project-specific lives in this repo.
