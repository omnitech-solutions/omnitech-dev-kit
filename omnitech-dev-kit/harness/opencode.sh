#!/usr/bin/env bash
# opencode adapter (OpenCode ≥1.3, `opencode run`). Called by run.py.
# env in: KIT_ROLE KIT_TOOLS KIT_MODEL KIT_THINKING KIT_OUT ; args: prompt parts (@files passed with --file).
# OpenCode has no CLI tool allow-list; restrictions live in the agent definition. The kit ships
# templates/opencode/agent/kit-<role>.md (permission: edit/bash deny for read-only roles). init_project.py
# copies them into <repo>/.opencode/agent/; this adapter selects --agent kit-<role> when that file exists
# and otherwise warns and runs the default agent (which is NOT tool-restricted).
# Model: -m provider/model (e.g. openrouter/z-ai/glm-5.3-flash). Reasoning: --variant low|medium|high.
# Sessions are always persisted by opencode; --title tags them so they can be found and pruned.
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
AGENT="kit-${KIT_ROLE:-worker}"
agent_args=()
if [[ -f ".opencode/agent/$AGENT.md" || -f ".opencode/agents/$AGENT.md" ]]; then agent_args=(--agent "$AGENT")
else echo "opencode adapter: no .opencode/agent/$AGENT.md in $PWD; tools are NOT restricted for this run" >&2; fi
file_args=(); while IFS= read -r f; do [[ -n "$f" ]] && file_args+=(--file "$f"); done < <(prompt_files "$@")
MSG="$(prompt_text "$@")"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
set +e
opencode run --dir "$PWD" ${KIT_MODEL:+-m "$KIT_MODEL"} ${KIT_THINKING:+--variant "$KIT_THINKING"} \
  ${agent_args[@]+"${agent_args[@]}"} ${file_args[@]+"${file_args[@]}"} --title "kit ${KIT_ROLE:-} ${KIT_UNIT:-}" "$MSG" | tee "$tmp"
rc=${PIPESTATUS[0]}
set -e
write_out "$tmp"
exit "$rc"
