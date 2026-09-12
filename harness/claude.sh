#!/usr/bin/env bash
# claude adapter: same role contract for Claude Code print mode. Called by run.py.
# env in: KIT_TOOLS KIT_APPROVAL KIT_MODEL KIT_OUT ; args: prompt parts (@files inlined here).
# Tool names translated: read→Read grep→Grep glob→Glob edit→Edit write→Write bash→Bash.
# --tools RESTRICTS the available built-in set (this is the boundary); --allowedTools only waives the
# permission prompt for those names. Both are passed: the first is the contract, the second keeps the
# run non-interactive. Everything not named is unavailable, not merely un-approved.
# Approval: yolo→bypassPermissions (only inside a worktree), else plan for read-only roles, default otherwise.
# Cost: Claude Code bills the Anthropic account, not OpenRouter; the JSON result carries total_cost_usd,
# which run.py reads when usage_probe is "harness".
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
map() { local t; for t in ${1//,/ }; do case $t in read) echo -n "Read ";; grep) echo -n "Grep ";; glob) echo -n "Glob ";; edit) echo -n "Edit ";; write) echo -n "Write ";; bash) echo -n "Bash ";; *) echo -n "$t ";; esac; done; }
TOOLS="$(map "$KIT_TOOLS")"
# --max-budget-usd is a HARD cap the CLI enforces itself, unlike the kit's post-run overrun report.
budget=(); [[ -n "${KIT_MAX_BUDGET_USD:-}" ]] && budget=(--max-budget-usd "$KIT_MAX_BUDGET_USD")
# Prefetch: "" disables every built-in tool, so the run is one turn over the supplied context.
if [[ "${KIT_NO_TOOLS:-0}" = "1" ]]; then TOOLS=""; fi
case "$KIT_APPROVAL" in
  yolo) PERM="bypassPermissions" ;;
  *) if [[ ",$KIT_TOOLS," == *",edit,"* || ",$KIT_TOOLS," == *",write,"* || ",$KIT_TOOLS," == *",bash,"* ]]; then PERM="default"; else PERM="plan"; fi ;;
esac
# A nested run must behave like a fresh terminal. When the kit is driven from inside a Claude Code
# session, the child inherits that session's wiring (ANTHROPIC_BASE_URL, messaging socket and token,
# session ids, SDK auth-delegation flags). Those belong to the host session, not to this run.
unset ANTHROPIC_BASE_URL CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_CHILD_SESSION \
      CLAUDE_CODE_MESSAGING_SOCKET CLAUDE_CODE_MESSAGING_TOKEN CLAUDE_CODE_SESSION_ID \
      CLAUDE_CODE_HOST_SESSION_ID CLAUDE_AGENT_SDK_VERSION CLAUDE_CODE_EXECPATH \
      CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH CLAUDE_CODE_SDK_HAS_OAUTH_REFRESH CLAUDE_CODE_OAUTH_SCOPES

# Fail closed on authentication BEFORE the run, so a logged-out CLI costs a second instead of a slot in
# the spend ledger. `claude auth status` is free and does not call a model.
if ! claude auth status 2>/dev/null | grep -q '"loggedIn": *true'; then
  echo "claude adapter: REFUSED — the claude CLI is not logged in (claude auth status reports loggedIn: false)." >&2
  echo "  This is the standalone CLI's own credential store; a Claude Code desktop session does not supply it." >&2
  echo "  fix: run 'claude setup-token' once in an interactive terminal and export CLAUDE_CODE_OAUTH_TOKEN," >&2
  echo "       or run 'claude' interactively and use /login. Then re-run this unit." >&2
  exit 77
fi

PROMPT="$(expand_prompt "$@")"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
set +e
if [[ "${KIT_NO_TOOLS:-0}" = "1" ]]; then
  claude -p ${KIT_MODEL:+--model "$KIT_MODEL"} --tools "" --permission-mode "$PERM" \
    ${budget[@]+"${budget[@]}"} --output-format json "$PROMPT" > "$tmp"
else
  claude -p ${KIT_MODEL:+--model "$KIT_MODEL"} --tools $TOOLS --allowedTools $TOOLS --permission-mode "$PERM" \
    ${budget[@]+"${budget[@]}"} --output-format json "$PROMPT" > "$tmp"
fi
rc=$?
set -e
# Print the assistant's final text as the run's stdout; keep the JSON (cost, turns) as the KIT_OUT sidecar.
python3 - "$tmp" <<'PY'
import json,sys
try:
    d=json.load(open(sys.argv[1])); print(d.get("result",""))
    print(f"\n[claude] cost_usd={d.get('total_cost_usd')} turns={d.get('num_turns')} duration_ms={d.get('duration_ms')}", file=sys.stderr)
except Exception: print(open(sys.argv[1]).read())
PY
[[ -n "${KIT_OUT:-}" ]] && { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("result",""))' "$tmp" > "$tmp.txt" 2>/dev/null || cp "$tmp" "$tmp.txt"; write_out "$tmp.txt"; rm -f "$tmp.txt"; }
[[ -n "${KIT_COST_FILE:-}" ]] && python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("total_cost_usd",0))' "$tmp" > "$KIT_COST_FILE" 2>/dev/null || true
exit "$rc"
