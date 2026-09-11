#!/usr/bin/env bash
# claude adapter: same role contract for Claude Code print mode. Called by run.py.
# Tool names are translated: read→Read grep→Grep glob→Glob edit→Edit write→Write bash→Bash
set -euo pipefail
map() { for t in ${1//,/ }; do case $t in read) echo -n "Read ";; grep) echo -n "Grep ";; glob) echo -n "Glob ";; edit) echo -n "Edit ";; write) echo -n "Write ";; bash) echo -n "Bash ";; *) echo -n "$t ";; esac; done; }
TOOLS="$(map "$KIT_TOOLS")"
PERM="default"; [ "$KIT_APPROVAL" = "yolo" ] && PERM="bypassPermissions"
# --max-time has no direct flag; run.py enforces the wall clock with a timeout.
exec claude -p ${KIT_MODEL:+--model "$KIT_MODEL"} --allowedTools $TOOLS --permission-mode "$PERM" "$*"
