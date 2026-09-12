#!/usr/bin/env bash
# _prompt.sh — shared helpers for harness adapters. Source, do not execute.
#
# expand_prompt "$@"  → prints one prompt body: every arg starting with '@' is a file whose
#                       contents are inlined under a "### <path>" heading; other args are kept
#                       verbatim, in order. Harnesses that do not expand @file (codex, claude -p,
#                       opencode message text) get the same context omp gets.
# prompt_files "$@"   → prints only the @file paths, one per line (for harnesses with --file).
# prompt_text "$@"    → prints only the non-@ args joined by newlines.
expand_prompt() {
  local a
  for a in "$@"; do
    if [[ "$a" == @* ]]; then
      local f="${a#@}"
      if [[ -f "$f" ]]; then
        printf '\n### %s\n\n' "$f"; cat "$f"; printf '\n'
      else
        echo "adapter: missing prompt file $f" >&2; return 2
      fi
    else
      printf '%s\n' "$a"
    fi
  done
}
prompt_files() { local a; for a in "$@"; do [[ "$a" == @* ]] && printf '%s\n' "${a#@}"; done; return 0; }
prompt_text()  { local a; for a in "$@"; do [[ "$a" != @* ]] && printf '%s\n' "$a"; done; return 0; }
# write_out FILE  → if KIT_OUT is set, copy FILE to it (the role's final answer artefact).
write_out() { [[ -n "${KIT_OUT:-}" && -f "$1" ]] && { mkdir -p "$(dirname "$KIT_OUT")"; cp "$1" "$KIT_OUT"; }; return 0; }
