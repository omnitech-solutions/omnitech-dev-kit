---
name: kit-write-packet
description: "Use when the user says \"write a packet for <row>\", \"packet <unit>\", or hands you one ledger row with oracle and subject fixtures and an evidence note. Produces exactly one execution packet in packets/TEMPLATE.md shape: exclusive owned files, todo DAG, structural evidence, real-boundary test, fail-closed DoD with counts, resume predicate, out-of-scope. Read-only; edits no code."
metadata:
  tags: "packets, orchestration, planning"
  bundles: "omnitech-dev-kit"
  risk_level: "low"
  companion_to: "crux"
---

# kit-write-packet

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
1. Read the project AGENTS file (from `promptbooks/AGENTS.template.md`), the ledger row, both fixtures, and `evidence/<row>.md` if present. If the evidence note is missing and the row needs code facts, stop and request a reader run first (`kit-run-unit`, role `reader`).
2. Follow `${KIT_PLUGIN_ROOT}/promptbooks/orchestrate.md` exactly; the output is the packet body only.
3. Save to the project's `packets/<unit>.md` and run `python3 ${KIT_PLUGIN_ROOT}/scripts/validate.py packet packets/<unit>.md --repo .`. A packet that fails validation is not a packet.
4. Hand the packet to the human. Status stays DRAFT until a human edits or approves it; never start an implementer on a DRAFT.

## Red flags
- §2 lists a file that does not exist and is not marked NEW.
- §3 contains a judgement call ("choose the best approach").
- §8 is empty or generic.
