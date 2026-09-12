#!/usr/bin/env bash
# codex adapter (OpenAI Codex CLI ≥0.150, `codex exec`). Called by run.py.
# env in: KIT_TOOLS KIT_APPROVAL KIT_MODEL KIT_THINKING KIT_OUT KIT_CODEX_PROVIDER ; args: prompt parts (@files inlined).
# Codex has no tool allow-list; the sandbox is the boundary:
#   roles that do not write source → --sandbox read-only
#   roles that write source        → --sandbox workspace-write, cwd = the worktree
#   danger-full-access is never emitted by this adapter.
# The sandbox is chosen from KIT_WRITES (set by run.py from the role's `writes` flag), NOT from whether
# "bash" appears in the tool list. A verifier needs bash to run gates but must not be able to edit the
# candidate it is judging; keying on bash handed it a writable workspace.
# KNOWN GAP (verified live 2026-09-10): read-only sandbox stops writes and network, but the model can
# still run shell commands to READ. A role whose tool list excludes bash is therefore not fully honoured
# here; run.py refuses such a role on codex unless the gap is recorded in kit.config.json.
# Approval: exec cannot answer prompts, so approval_policy=never; the sandbox, not the prompt, refuses.
# No session: --ephemeral. Model: -m; provider via KIT_CODEX_PROVIDER (e.g. "openrouter" defined in
# ~/.codex/config.toml with base_url https://openrouter.ai/api/v1 and env_key OPENROUTER_API_KEY).
# Reasoning: KIT_THINKING low|medium|high → model_reasoning_effort.
# Provider: KIT_CODEX_PROVIDER names it. If KIT_CODEX_BASE_URL is also set, the provider is DEFINED
# inline with -c flags so the user's ~/.codex/config.toml is never modified by the kit. The API key is
# passed by NAME only (KIT_CODEX_ENV_KEY, default OPENROUTER_API_KEY); its value never reaches the CLI.
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
if [[ "${KIT_WRITES:-}" = "1" ]]; then SANDBOX="workspace-write"
elif [[ -z "${KIT_WRITES:-}" && ( ",$KIT_TOOLS," == *",edit,"* || ",$KIT_TOOLS," == *",write,"* ) ]]; then SANDBOX="workspace-write"
else SANDBOX="read-only"; fi
prov=()
if [[ -n "${KIT_CODEX_PROVIDER:-}" ]]; then
  prov+=(-c "model_provider=\"$KIT_CODEX_PROVIDER\"")
  if [[ -n "${KIT_CODEX_BASE_URL:-}" ]]; then
    prov+=(-c "model_providers.$KIT_CODEX_PROVIDER.name=\"$KIT_CODEX_PROVIDER\"")
    prov+=(-c "model_providers.$KIT_CODEX_PROVIDER.base_url=\"$KIT_CODEX_BASE_URL\"")
    prov+=(-c "model_providers.$KIT_CODEX_PROVIDER.env_key=\"${KIT_CODEX_ENV_KEY:-OPENROUTER_API_KEY}\"")
  fi
fi
PROMPT="$(expand_prompt "$@")"
last="$(mktemp)"; trap 'rm -f "$last"' EXIT
set +e
codex exec --ephemeral --skip-git-repo-check -C "$PWD" --sandbox "$SANDBOX" --color never \
  -c 'approval_policy="never"' \
  ${KIT_MODEL:+-m "$KIT_MODEL"} \
  ${prov[@]+"${prov[@]}"} \
  ${KIT_THINKING:+-c "model_reasoning_effort=\"$KIT_THINKING\""} \
  -o "$last" "$PROMPT"
rc=$?
set -e
echo; echo "### final message"; cat "$last" 2>/dev/null || true
write_out "$last"
exit "$rc"
