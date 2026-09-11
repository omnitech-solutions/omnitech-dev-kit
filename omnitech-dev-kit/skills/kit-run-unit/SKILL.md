---
name: kit-run-unit
description: "Use when the user says \"run unit <id> as <role>\", \"start the reader/orchestrator/implementer/verifier\", or wants one cost-guarded model run through omp or Claude Code. Wraps scripts/run.py: role tool allow-list, wall-clock cap, no session, stdin from /dev/null, per-run and per-campaign dollar guards, one spend row. Never loops; one human command, one run."
metadata:
  tags: "runner, cost-guard, harness"
  bundles: "omnitech-dev-kit"
  risk_level: "medium"
  companion_to: "crux"
---

# kit-run-unit

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
1. Confirm `kit.config.json` exists in the project's kit folder (copy `kit.config.example.json`; set `campaign_baseline_usd` to the current key usage before the first run). The key is read from the env var named by `key_env`; never read it from dotfiles or print it.
2. Build the prompt as `@` file references: the AGENTS file, the role promptbook from `${KIT_PLUGIN_ROOT}/promptbooks/`, the packet or fixtures, then one line of instruction naming the receipt path.
3. Run: `python3 ${KIT_PLUGIN_ROOT}/scripts/run.py <role> <unit> <cwd> [--harness omp|claude] [--model M] [--thinking low] -- @... "instruction"`.
4. Read the one-line result. Exit 3 or 4 means a guard fired: stop and report; do not retry.
5. Implementer runs happen in a git worktree the human created (`git worktree add -b <unit> ../wt-<unit> <branch>`); the verifier runs in the same worktree afterwards.

## Never
Start a run inside a loop or scheduler. Raise a cap to make a run pass. Run an implementer against the main checkout.
