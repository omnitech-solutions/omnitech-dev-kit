#!/usr/bin/env bash
# codex adapter (OpenAI Codex CLI ≥0.150, `codex exec`). Called by run.py.
# env in: KIT_TOOLS KIT_APPROVAL KIT_MODEL KIT_THINKING KIT_OUT KIT_CODEX_PROVIDER ; args: prompt parts (@files inlined).
# Codex has no tool allow-list; the sandbox is the boundary:
#   read-only roles (no edit/write/bash in KIT_TOOLS) → --sandbox read-only
#   writing roles                                     → --sandbox workspace-write, cwd = the worktree
#   danger-full-access is never emitted by this adapter.
# Approval: exec cannot answer prompts, so approval_policy=never; the sandbox, not the prompt, refuses.
# No session: --ephemeral. Model: -m; provider via KIT_CODEX_PROVIDER (e.g. "openrouter" defined in
# ~/.codex/config.toml with base_url https://openrouter.ai/api/v1 and env_key OPENROUTER_API_KEY).
# Reasoning: KIT_THINKING low|medium|high → model_reasoning_effort.
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
if [[ ",$KIT_TOOLS," == *",edit,"* || ",$KIT_TOOLS," == *",write,"* || ",$KIT_TOOLS," == *",bash,"* ]]; then SANDBOX="workspace-write"; else SANDBOX="read-only"; fi
PROMPT="$(expand_prompt "$@")"
last="$(mktemp)"; trap 'rm -f "$last"' EXIT
set +e
codex exec --ephemeral --skip-git-repo-check -C "$PWD" --sandbox "$SANDBOX" --color never \
  -c 'approval_policy="never"' \
  ${KIT_MODEL:+-m "$KIT_MODEL"} \
  ${KIT_CODEX_PROVIDER:+-c "model_provider=\"$KIT_CODEX_PROVIDER\""} \
  ${KIT_THINKING:+-c "model_reasoning_effort=\"$KIT_THINKING\""} \
  -o "$last" "$PROMPT"
rc=$?
set -e
echo; echo "### final message"; cat "$last" 2>/dev/null || true
write_out "$last"
exit "$rc"
