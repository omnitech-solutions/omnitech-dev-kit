---
name: kit-verify-receipt
description: "Use when an implementer run has finished in a worktree and the user says \"verify <unit>\", \"check the receipt\", or \"is this done\". Runs the verifier promptbook: scope guard, re-run of the declared gates, verify-test-teeth on new tests, local-diff-review, packet §8 conformance; writes receipts/<unit>-receipt.md whose first line is VERDICT: ACCEPT or VERDICT: REJECT. Treats the execution record as a claim."
metadata:
  tags: "verification, receipts, fail-closed"
  bundles: "omnitech-dev-kit"
  risk_level: "low"
  companion_to: "crux"
---

# kit-verify-receipt

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
1. Work in the implementer's worktree, never the main checkout. Inputs: the AGENTS file, the packet, `receipts/<unit>-execution.md`, and the borrowed skills `verify-test-teeth`, `local-diff-review`, `record-gate-evidence`, `commit-scope-guard` under `${KIT_PLUGIN_ROOT}/skills/borrowed/`.
2. Follow `${KIT_PLUGIN_ROOT}/promptbooks/verify.md` exactly.
3. Run `python3 ${KIT_PLUGIN_ROOT}/scripts/validate.py receipt receipts/<unit>-receipt.md`.
4. An ACCEPT is a model verdict. Say so explicitly: the human live-boundary gate named in packet §6 is still owed. Never write "done".
5. Then run `kit-record-evaluation` for each borrowed skill you applied (`used`), and at session end an `evaluated` entry for any that changed the verdict.
