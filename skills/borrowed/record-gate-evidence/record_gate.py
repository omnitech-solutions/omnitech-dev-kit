# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""record_gate.py — run a quality gate and emit the canonical run-notes evidence line.

ADR-0013/0014-era discipline (see the record-gate-evidence SKILL.md): the recorded gate evidence
must carry the exact command + the scope + a concrete result token, never a bare "green". This
helper runs the gate (argv form, no shell) and prints the canonical line to paste into a run
snapshot's Notes. It does NOT judge whether the gate you ran is the declared merge bar — that is
the skill's prose discipline (read the Makefile's `check` target and run exactly that).

Usage:  uv run record_gate.py -- <gate command argv...>
  e.g.: uv run record_gate.py -- make check
        uv run record_gate.py -- uv run pytest tests -q
"""

from __future__ import annotations

import re
import subprocess
import sys

# The result-token patterns, in priority order — the first match wins. Each captures the token that
# a reviewer would corroborate against the diff (a count, an OK, an exit-clean phrase). The full
# pytest summary (which leads with failures when there are any) is preferred over a bare pass count.
_TOKEN_PATTERNS = [
    re.compile(r"((?:\d+ failed, )?\d+ passed(?:, \d+ (?:failed|skipped|deselected|warnings?|errors?))*)"),
    re.compile(r"(\d+ failed)"),
    re.compile(r"(Success: no issues found in \d+ source files)"),
    re.compile(r"(All checks passed!)"),
    re.compile(r"(\d+ files? (?:already formatted|would be reformatted))"),
    re.compile(r"(no issues identified)", re.IGNORECASE),
    re.compile(r"\b(OK)\b"),
]


def _extract_token(output: str) -> str:
    """The last matching result token in the output (a gate's summary is at the end)."""
    for pat in _TOKEN_PATTERNS:
        matches = pat.findall(output)
        if matches:
            return matches[-1]
    # No known token: report the tail so the record is never token-less.
    tail = [l for l in output.strip().splitlines() if l.strip()]
    return tail[-1].strip()[:120] if tail else "(no output)"


def main(argv: list[str]) -> int:
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    if not argv:
        print("usage: record_gate.py -- <gate command argv...>", file=sys.stderr)
        return 2
    cmd = argv
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603 — argv form, no shell
    output = proc.stdout + proc.stderr
    token = _extract_token(output)
    command_str = " ".join(cmd)
    scope = "repo root" if "check" in cmd or "make" in cmd else " ".join(cmd[1:])[:40]
    verdict = "exit 0" if proc.returncode == 0 else f"exit {proc.returncode} (FAIL)"
    # The canonical evidence line: command + scope + exit + result token.
    print(f"gate: `{command_str}` ({scope}) → {verdict} — {token}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
