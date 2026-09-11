# Compatibility contract with crux

crux is upstream and is regenerated per release; it accepts no pull requests. This kit must
survive any crux update without edits to crux. Rules:

1. **No vendoring.** No file from `bionic-coding/crux` is copied here except the generated
   `runtime-compat` block, reproduced verbatim inside each kit SKILL.md as crux does.
2. **Pinned floor, not a fork.** `plugin.json` declares `requires.crux`. `kit-check-crux-compat`
   reads the installed crux `plugin.json` and fails below the floor.
3. **Namespace.** Every kit skill id starts with `kit-`. `kit-check-crux-compat` diffs kit skill
   ids against the installed crux `catalog/skills.json` and fails on any collision, because
   crux's forge collision rule forbids a local skill shadowing a plugin skill.
4. **Forge-log format is crux's.** The seven-event enum, header regex `^## \[\d{4}-\d{2}-\d{2}
   \d{2}:\d{2}\] (authored|revised|used|evaluated|fallback|escalated|pruned) \| [a-z0-9][a-z0-9-]*$`,
   and the two-line `evaluated` exemplar are copied from crux `forge-skill/SKILL.md`. The compat
   check greps the installed crux for that enum string and fails if it changed, so a format
   change upstream is caught, not silently diverged from.
5. **Recording surfaces.** Kit skills write only to: the kit `forge-log.md`, the consuming
   project's kit folder (`packets/`, `receipts/`, `evidence/`, `runs/`, `spend.md`), and, when
   the project is crux-managed, through crux's own front doors (`log-work`, `process-inbox`) —
   never directly into `bionic/`.
6. **Do not reimplement crux.** forge-skill, retrospective, council, ADRs, promptbook run
   snapshots come from crux. The kit consumes them; `kit-record-evaluation` exists only so a
   non-crux session (e.g. OMP) can still write a compliant forge-log entry.
7. **Upstream changes go back as proposals.** A needed change to crux is filed as a
   contract-amendment proposal in `inbox/` (Mark's harvester pattern) and, if universally
   useful, as an issue on the crux repo. Never patch crux locally.
8. **Runtime compatibility.** Kit skills carry crux's generated `runtime-compat` block so they
   are portable across Claude Code, Codex, and OpenCode with the same `CRUX_PLUGIN_ROOT` /
   `CRUX_LOCAL_SKILLS_DIR` conventions. Add `KIT_PLUGIN_ROOT` the same way.

Verified against crux **3.11.1** (2026-09-10). Re-run `python3 omnitech-dev-kit/scripts/check_crux_compat.py`
after every crux upgrade and record the result in `forge-log.md` as a `used | kit-check-crux-compat` entry.
