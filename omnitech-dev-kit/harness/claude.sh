#!/usr/bin/env bash
# claude adapter: same role contract for Claude Code print mode. Called by run.py.
# env in: KIT_TOOLS KIT_APPROVAL KIT_MODEL KIT_OUT ; args: prompt parts (@files inlined here).
# Tool names translated: read→Read grep→Grep glob→Glob edit→Edit write→Write bash→Bash.
# Approval: yolo→bypassPermissions (only inside a worktree), else plan for read-only roles, default otherwise.
# Cost: Claude Code bills the Anthropic account, not OpenRouter; the JSON result carries total_cost_usd,
# which run.py reads when usage_probe is "harness".
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
map() { local t; for t in ${1//,/ }; do case $t in read) echo -n "Read ";; grep) echo -n "Grep ";; glob) echo -n "Glob ";; edit) echo -n "Edit ";; write) echo -n "Write ";; bash) echo -n "Bash ";; *) echo -n "$t ";; esac; done; }
TOOLS="$(map "$KIT_TOOLS")"
case "$KIT_APPROVAL" in
  yolo) PERM="bypassPermissions" ;;
  *) if [[ ",$KIT_TOOLS," == *",edit,"* || ",$KIT_TOOLS," == *",write,"* || ",$KIT_TOOLS," == *",bash,"* ]]; then PERM="default"; else PERM="plan"; fi ;;
esac
PROMPT="$(expand_prompt "$@")"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
set +e
claude -p ${KIT_MODEL:+--model "$KIT_MODEL"} --allowedTools $TOOLS --permission-mode "$PERM" \
  --output-format json "$PROMPT" > "$tmp"
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
