# INIT — starting orchestration on a new feature or a new project

This is the whole bootstrap, in order, with the time each step takes when done properly. Nothing here
is optional; each step exists because skipping it cost money or a false green in the pilot. Budget
**about 90 minutes** from zero to the first verified unit on a repo you know; half that on the second feature.

## 0. Preconditions (10 min, once per machine)
- Python 3.11+. One harness on PATH: `omp`, `claude`, `codex` or `opencode` (see HARNESSES.md for setup).
- The kit checked out, `export KIT_PLUGIN_ROOT=<checkout>/omnitech-dev-kit`. Claude Code users may install it as
  a plugin instead (README); OMP users run `python3 $KIT_PLUGIN_ROOT/scripts/sync_skills.py` once.
- The model key exported in the shell that will run units, under the name `kit.config.json` will reference
  (default `OPENROUTER_API_KEY`). Never in the kit, never in a repo, never grepped out of a dotfile.
- Optional: crux installed if the project keeps a `bionic/` tree; `python3 scripts/check_crux_compat.py` passes.

## 1. Decide the oracle and the subject (15 min, human, no model)
Write two sentences you could defend to a stranger:
- **Oracle**: the system whose behaviour is the target (a reference product, a spec, a prior version, a design).
  Where a human may look at it, and the hard rules for looking (in the pilot: one playground survey, never
  publish, never email, never share).
- **Subject**: the system being changed and where its current behaviour can be captured (URL, build, command).
Models never see the oracle. Humans freeze fixtures. If you cannot capture a fixture pair for a behaviour, it
is not a ledger row yet.

## 2. Scaffold the campaign folder (2 min)
```bash
python3 $KIT_PLUGIN_ROOT/scripts/init_project.py <repo> <campaign-dir> --feature <slug> --harness <omp|claude|codex|opencode> \
  --oracle "<one line>" --baseline-usd <current key usage> [--models reader=…,orchestrator=…,implementer=…,verifier=…]
```
Convention: `<campaign-dir>` = `.<owner>/kit/<feature>/` (gitignored, one owner) or `kit/<feature>/` (committed,
a team). Decide once per repo. The scaffold prints the checklist; the rest of this file is that checklist expanded.

## 3. Fill the entry law: `AGENTS-<feature>.md` (20 min, the most valuable minutes of the campaign)
- **Mission**: one paragraph, from step 1.
- **Boundary**: the owned directories. Protected inputs by path: lockfiles, CI, settings, sanitizers, schemas,
  every test not named in a packet.
- **Invariants**: 2–5 domain rules a change must not break. Write them as things a verifier can check.
- **Gates table**: the exact commands and their **baseline counts from a real run today**. `pnpm test` is not a
  gate; `pnpm test:product → 670 passed, 0 failed` is. Include one **live-boundary gate** that only a human or an
  e2e run can execute; mark it so.
- **Receipts** and **Stop conditions**: keep the template text; it is already the pilot's wording.
A model reads this file on every run. Every line that is vague here becomes a judgement call a fast model makes
badly at 3 a.m.

## 4. Capture the first fixtures and write the ledger (20–40 min per 3–5 rows, human)
One fixture pair per observable behaviour: `fixtures/oracle/<ROW>.md` and `fixtures/subject/<ROW>.md`, plain
markdown: what is on screen, what happens on click, exact labels, DOM classes or selectors if the subject is a
web UI. Then one ledger row each, verdict `UNCAPTURED` → `FAIL`/`PARTIAL` once compared. Cap the ledger (the
pilot: 8 rows, extended only by owner request). `validate.py ledger ledger.md --repo <campaign-dir>` must pass.

## 5. Config and a dry run (3 min)
- `kit.config.json`: `campaign_baseline_usd` = key usage now; caps you can afford to lose entirely; models per role
  (defaults: Flash-class for reader/implementer/verifier, one tier up for the orchestrator).
- `run.py … --dry-run` once. It prints the adapter, the `KIT_*` env and the prompt parts. Read them.

## 6. The first unit (25–40 min, mostly waiting)
Follow the generated `RUNBOOK.md` for row 1: reader → evidence → orchestrator → **you edit the packet** (status
REVIEWED; delete anything you would not defend) → worktree → implementer → verifier → **you run the live gate**
→ commit from the main checkout. Read `lessons/` in the kit once before this; each one is a minute you will not
have to lose again.

## 7. Close the unit (3 min)
- Ledger row: verdict, unit id, gate state ("COMMITTED (verifier ACCEPT; live PASS)").
- `spend.md`: a "Unit totals" line (run.py writes the rows; the human writes the total).
- `kit-record-evaluation`: one `used` entry per borrowed skill the verifier applied; an `evaluated` entry if a
  skill changed the verdict. This is the only way the kit learns which disciplines pay.
- Anything you learned that is not project-specific: a dated file in `lessons/`. Project-specific: a line in the
  campaign RUNBOOK.

## Second feature, same repo (15 min)
Steps 2, 3 (copy the previous AGENTS file, change mission, owned dirs, and the gates baseline), 4, 5. The
harness, config shape and RUNBOOK are the same; only the entry law and fixtures are new.

## Second project (30 min)
Steps 0 (if a new machine or harness), 1–5. Nothing from the first project is copied except lessons, and those
are already in the kit.

## Signs the init was skipped
- A packet §2 names a file that does not exist → step 3 or the reader was skipped.
- The verifier's gate lines have no counts → step 3 gates table was vague.
- The first unit's receipt says ACCEPT and the feature does not work → step 3 has no live-boundary gate.
- Spend rows show `cost 0.0000` with a paid model → step 5 key/probe mismatch.
