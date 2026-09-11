---
name: kit-check-crux-compat
description: "Use after installing or upgrading crux, or when the user says \"check crux compat\", \"is the kit still compatible\", or before releasing a kit version. Runs scripts/check_crux_compat.py: crux version floor, skill-id collisions against the crux catalog, forge-log enum and exemplar presence in crux forge-skill, runtime-compat block parity. Read-only."
metadata:
  tags: "compat, crux, release-gate"
  bundles: "omnitech-dev-kit"
  risk_level: "low"
  companion_to: "crux"
---

# kit-check-crux-compat

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
1. `python3 ${KIT_PLUGIN_ROOT}/scripts/check_crux_compat.py [--crux-root DIR]` (exit 2 means crux was not found: set `CRUX_PLUGIN_ROOT`).
2. On INCOMPATIBLE: do not patch crux. Fix the kit (rename a colliding skill, regenerate the runtime-compat block, update the format the kit validates) or file a contract-amendment proposal in `inbox/` per `COMPAT.md` §7.
3. Record the outcome with `kit-record-evaluation` as `used | kit-check-crux-compat`.
