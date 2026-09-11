---
name: kit-record-evaluation
description: "Use when the user says \"record evaluation for <skill>\", \"log that <skill> was used\", or at the end of a session that applied a borrowed or kit skill. Appends one entry to the kit forge-log.md in crux forge-skill's locked seven-event format (used | evaluated | fallback | escalated only; lifecycle events belong to crux forge-skill). Exists so non-crux sessions such as omp still leave evidence."
metadata:
  tags: "forge-log, evidence, learning"
  bundles: "omnitech-dev-kit"
  risk_level: "low"
  companion_to: "crux"
---

# kit-record-evaluation

<!-- BEGIN GENERATED: runtime-compat -->
## Runtime compatibility

This skill is portable across Claude Code, Codex, and OpenCode. This section overrides platform-specific labels below.

- Before running a command that uses `CRUX_PLUGIN_ROOT`, set it to the installed plugin root. In Claude Code, use the value of `CLAUDE_PLUGIN_ROOT`. In Codex and OpenCode, derive it from the absolute path of this selected `SKILL.md`: the plugin root is the parent of its `skills/` directory. In a source checkout, use the checkout `crux/` directory.
- For project-local skills, use `.claude/skills` in Claude Code, `.agents/skills` in Codex, and `.opencode/skills` in OpenCode, which also reads the singular `.opencode/skill`. Set `CRUX_LOCAL_SKILLS_DIR` to that path before following any command below that uses it.
- Translate Claude Code tool labels such as `Agent`, `Read`, `Write`, `Bash`, `WebSearch`, and `WebFetch` to the matching capability in the current session. Codex names its own capabilities; OpenCode uses the lowercase forms `subagent`, `read`, `edit`, `shell`, `websearch`, and `webfetch`, where `edit` covers both `Edit` and `Write`. Do not attempt to invoke the Claude Code labels as literal commands on another host.
- Install the generated role agents before delegating: `install-codex-agents` in Codex, `install-opencode-agents` in OpenCode. Codex names them `crux_architect`, `crux_brainstormer`, `crux_commander`, `crux_dev_lead`, `crux_developer`, `crux_historian`, `crux_librarian`, `crux_night_gardener`, `crux_reviewer`, and `crux_wayfinder`; OpenCode uses the bare role names `architect`, `brainstormer`, `commander`, `dev-lead`, `developer`, `historian`, `librarian`, `night-gardener`, `reviewer`, and `wayfinder`. If a required role or capability is unavailable, report that truthfully instead of claiming it ran.
- Argument placeholders such as `$adr` and `$book` bind only in Claude Code. On a host without argument binding they are unset — take the value from the user's phrase. The "Fields OpenCode ignores" section of `OPENCODE_GUIDE.md` names the invocation-control fields OpenCode ignores.
<!-- END GENERATED: runtime-compat -->

## Contract
The log is `<kit repo>/forge-log.md`. Format is crux's, verbatim:

```
## [YYYY-MM-DD HH:MM] <event> | <skill-name>
```
followed by 1–3 single-line body lines that never begin with `## [`. For `evaluated` exactly:
```
- verdict: effective | gap: closed | recommend: keep
- evidence: <one line, the harvestable quote; name the project here>
```
verdict ∈ effective, fell-short, mixed; gap ∈ closed, partial, not-closed; recommend ∈ keep, revise, prune.
`used` body: task one-liner + `ok` or `partial`. Entries newest-first, inserted after the preamble.

## Procedure
1. Compose the entry; summarise in your own words, never paste tool output (it can embed tokens).
2. Insert it as the first entry after the preamble paragraphs.
3. Run `python3 ${KIT_PLUGIN_ROOT}/scripts/validate.py forge-log <path>`; fix or remove an invalid entry before ending.
4. Never write `authored`, `revised`, or `pruned`; those are crux forge-skill's. A skill gap you noticed goes to the project inbox for crux `forge-skill` or `retrospective`.
