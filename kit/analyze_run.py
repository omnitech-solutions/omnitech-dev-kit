#!/usr/bin/env python3
"""analyze_run.py — read one run log and report loop / truncation symptoms (stdlib only).

usage: analyze_run.py <log-file> [--json] [--repeat-threshold N]

Why: a model whose context window is too small for the prompt gets its instructions truncated,
forgets what it was doing, and re-issues the same tool call forever. The run then dies on the wall
clock with no artefact. The symptom is visible in the log even when the harness reports success:
the same tool line repeated many times, and no final answer.

Detects:
  repeated_tool_calls  the most-repeated normalised tool line and how often it occurs
  loop_suspected       that count >= --repeat-threshold (default 5)
  truncation_markers   provider/runtime phrases that mean the prompt was cut
  distinct_tools       how many different tool lines appeared (a loop has few)
exit 0 nothing suspicious, 1 loop suspected or truncation seen, 2 usage.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Tool markers per harness. omp/opencode print arrows and bullets; codex echoes the shell command it is
# about to run, prefixed by the shell path; claude's JSON output carries no per-call lines at all.
TOOL_LINE = re.compile(r"^\s*(?:[→✱↳•]|tool:|Tool:|\[tool\])\s*(.+)$")
CODEX_EXEC = re.compile(r"^\s*(?:/[\w./-]*)?(?:ba|z)?sh\s+-l?c\s+(.+?)(?:\s+in\s+/.*)?$")
# Harnesses whose logs carry no tool lines at all: absence of repeats there means "unknown", not "healthy".
OPAQUE_HINTS = ("harness=claude",)
TRUNCATION = [
    "TruncateMiddle", "rolling window policy", "context window", "context_length_exceeded",
    "prompt is too long", "maximum context length", "truncat",
]

def analyze(path, threshold=5):
    raw = Path(path).read_text(errors="replace")
    lines = [ANSI.sub("", l).rstrip() for l in raw.splitlines()]
    tools = []
    for l in lines:
        m = TOOL_LINE.match(l) or CODEX_EXEC.match(l)
        if m:
            # drop trailing per-call noise (offsets, match counts) so re-reads normalise together
            t = re.sub(r"\s*\[[^\]]*\]\s*$", "", m.group(1)).strip()
            t = re.sub(r"·.*$", "", t).strip()
            if t: tools.append(t)
    counts = Counter(tools)
    top, n = (counts.most_common(1)[0] if counts else ("", 0))
    markers = sorted({w for w in TRUNCATION if w.lower() in raw.lower()})
    opaque = (not tools) and any(h in raw for h in OPAQUE_HINTS)
    return {
        "log": str(path),
        "observable": not opaque,
        "tool_calls": len(tools),
        "distinct_tools": len(counts),
        "top_repeat": top,
        "top_repeat_count": n,
        "loop_suspected": n >= threshold,
        "truncation_markers": markers,
    }

def main(a):
    if not a: print(__doc__, file=sys.stderr); return 2
    path = a[0]
    if not Path(path).is_file(): print(f"analyze_run: no log {path}", file=sys.stderr); return 2
    th = int(a[a.index("--repeat-threshold") + 1]) if "--repeat-threshold" in a else 5
    r = analyze(path, th)
    if "--json" in a:
        print(json.dumps(r))
    else:
        if not r["observable"]:
            print("this harness does not log individual tool calls; loop detection is UNAVAILABLE for this run")
        print(f"tool calls {r['tool_calls']} across {r['distinct_tools']} distinct; "
              f"most repeated {r['top_repeat_count']}× {r['top_repeat']!r}")
        if r["loop_suspected"]:
            print("LOOP SUSPECTED: the same tool call repeats. Usual cause: the prompt exceeds the "
                  "model's context window, so its instructions were truncated away. Shrink the prompt, "
                  "raise the model's context limit, or use a larger model. Do not re-run unchanged.")
        for m in r["truncation_markers"]: print(f"TRUNCATION MARKER: {m!r} appears in the log")
    return 1 if (r["loop_suspected"] or r["truncation_markers"]) else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
