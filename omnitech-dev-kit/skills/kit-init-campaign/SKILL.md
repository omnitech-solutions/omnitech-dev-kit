---
name: kit-init-campaign
description: "Use when the user says \"start orchestration for <feature>\", \"set up the kit on <repo>\", \"init a campaign\", or wants to begin packet/receipt work on a new feature or project. Runs scripts/init_project.py to scaffold the campaign folder (OBJECTIVE, AGENTS-<feature>, ledger, kit.config, RUNBOOK for the chosen harness, fixtures/evidence/packets/receipts/runs, spend) and walks the human checklist in docs/INIT.md. Edits no product code."
metadata:
  tags: "bootstrap, campaign, init"
  bundles: "omnitech-dev-kit"
  risk_level: "low"
  companion_to: "crux"
---

# kit-init-campaign

<!-- BEGIN GENERATED: runtime-compat -->
## Runtime compatibility

This skill is portable across Claude Code, Codex, and OpenCode. This section overrides platform-specific labels below.

- Before running a command that uses `CRUX_PLUGIN_ROOT`, set it to the installed plugin root. In Claude Code, use the value of `CLAUDE_PLUGIN_ROOT`. In Codex and OpenCode, derive it from the absolute path of this selected `SKILL.md`: the plugin root is the parent of its `skills/` directory. In a source checkout, use the checkout `crux/` directory.
- For project-local skills, use `.claude/skills` in Claude Code, `.agents/skills` in Codex, and `.opencode/skills` in OpenCode, which also reads the singular `.opencode/skill`. Set `CRUX_LOCAL_SKILLS_DIR` to that path before following any command below that uses it.
- Translate Claude Code tool labels such as `Agent`, `Read`, `Write`, `Bash`, `WebSearch`, and `WebFetch` to the matching capability in the current session. Codex names its own capabilities; OpenCode uses the lowercase forms `subagent`, `read`, `edit`, `shell`, `websearch`, and `webfetch`, where `edit` covers both `Edit` and `Write`. Do not attempt to invoke the Claude Code labels as literal commands on another host.
- Install the generated role agents before delegating: `install-codex-agents` in Codex, `install-opencode-agents` in OpenCode. Codex names them `crux_architect`, `crux_brainstormer`, `crux_commander`, `crux_dev_lead`, `crux_developer`, `crux_historian`, `crux_librarian`, `crux_night_gardener`, `crux_reviewer`, and `crux_wayfinder`; OpenCode uses the bare role names `architect`, `brainstormer`, `commander`, `dev-lead`, `developer`, `historian`, `librarian`, `night-gardener`, `reviewer`, and `wayfinder`. If a required role or capability is unavailable, report that truthfully instead of claiming it ran.
- Argument placeholders such as `$adr` and `$book` bind only in Claude Code. On a host without argument binding they are unset — take the value from the user's phrase. The "Fields OpenCode ignores" section of `OPENCODE_GUIDE.md` names the invocation-control fields OpenCode ignores.
<!-- END GENERATED: runtime-compat -->

## Procedure
1. Ask for, or take from the user's phrase: repo path, feature slug (kebab-case), harness (omp|claude|codex|opencode), one-line oracle. Read the current key usage if the probe is OpenRouter (never print the key).
2. Run `python3 ${KIT_PLUGIN_ROOT}/scripts/init_project.py <repo> <campaign-dir> --feature <slug> --harness <h> --oracle "<line>" --baseline-usd <usage>`. Never pass `--force` unless the user asked to overwrite.
3. Open `docs/INIT.md` §3 with the user and fill `AGENTS-<feature>.md`: owned dirs, protected inputs, invariants, gates table with baseline counts from a real run **today**, one live-boundary gate.
4. Capture the first fixture pair together (human does the capturing; you write the ledger row). `validate.py ledger` must pass.
5. `run.py <role> … --dry-run` once; hand the RUNBOOK to the user. The first paid run is the human's command, not yours.

## Never
Write fixtures from memory or from the oracle directly. Invent baseline counts. Start a paid run from inside this skill.
