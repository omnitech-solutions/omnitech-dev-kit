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
if [[ "${KIT_NO_TOOLS:-0}" = "1" ]]; then
  echo "opencode adapter: REFUSED — prefetch needs a no-tools agent; opencode expresses tool limits only" >&2
  echo "  through an agent file and the kit does not ship a kit-prefetch agent yet. Use omp or claude." >&2
  exit 77
fi
AGENT="kit-${KIT_ROLE:-worker}"
# FAIL CLOSED. The agent file is the ONLY place OpenCode expresses this role's tool limits. Running the
# default agent instead would silently give an unrestricted session. Install the agents with
# scripts/init_project.py --harness opencode, or set KIT_OPENCODE_ALLOW_DEFAULT_AGENT=1 to accept the gap.
if [[ -f ".opencode/agent/$AGENT.md" || -f ".opencode/agents/$AGENT.md" ]]; then
  agent_args=(--agent "$AGENT")
elif [[ "${KIT_OPENCODE_ALLOW_DEFAULT_AGENT:-0}" = "1" ]]; then
  agent_args=()
  echo "opencode adapter: no $AGENT.md; running the DEFAULT agent unrestricted because KIT_OPENCODE_ALLOW_DEFAULT_AGENT=1" >&2
else
  echo "opencode adapter: REFUSED — no .opencode/agent/$AGENT.md in $PWD, so the $KIT_ROLE role's tool limits cannot be applied." >&2
  echo "  fix: python3 \$KIT_PLUGIN_ROOT/scripts/init_project.py <repo> <campaign> --feature <f> --harness opencode" >&2
  exit 78
fi
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
