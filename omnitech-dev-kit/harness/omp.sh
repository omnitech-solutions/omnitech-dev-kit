#!/usr/bin/env bash
# omp adapter (Oh-My-Pi ≥18): translate kit role settings into omp flags. Called by run.py.
# env in: KIT_TOOLS KIT_MAX_TIME KIT_APPROVAL KIT_MODEL KIT_THINKING KIT_OUT ; args: prompt parts (@files and text)
# omp expands @file itself; tool names are omp's (read,grep,glob,write,edit,bash,find,task,todo).
# --max-time is honoured by omp AND enforced again by run.py's wall clock.
set -euo pipefail
. "$(dirname "$0")/_prompt.sh"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
set +e
omp --no-session --print \
  ${KIT_MODEL:+--model "$KIT_MODEL"} ${KIT_THINKING:+--thinking "$KIT_THINKING"} \
  --tools "$KIT_TOOLS" --approval-mode "$KIT_APPROVAL" --max-time "$KIT_MAX_TIME" "$@" | tee "$tmp"
rc=${PIPESTATUS[0]}
set -e
write_out "$tmp"   # omp -p prints the final answer (plus tool lines) to stdout; KIT_OUT gets that stream
exit "$rc"
