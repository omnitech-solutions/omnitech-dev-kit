#!/usr/bin/env bash
# omp adapter: translate kit role settings into omp flags. Called by run.py.
# env in: KIT_TOOLS KIT_MAX_TIME KIT_APPROVAL KIT_MODEL KIT_THINKING ; args: prompt parts (@files and text)
set -euo pipefail
exec omp --no-session --print \
  ${KIT_MODEL:+--model "$KIT_MODEL"} ${KIT_THINKING:+--thinking "$KIT_THINKING"} \
  --tools "$KIT_TOOLS" --approval-mode "$KIT_APPROVAL" --max-time "$KIT_MAX_TIME" "$@"
