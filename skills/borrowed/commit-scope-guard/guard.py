# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""commit-scope-guard — before a cycle commit, flag changed/staged files that
fall OUTSIDE the cycle's intended file set.

Pure stdlib (no third-party deps). STRICTLY READ-ONLY and ADVISORY: it runs
`git status` only, prints a review list, and NEVER stages, restores, resets, or
otherwise mutates the tree or the index. It always exits 0 — it is a review aid,
not a gate that acts. The human decides what to exclude from the commit.

Usage:
    python3 guard.py <intended-path-or-prefix> [<intended...>]

Each intended argument is either an exact repo-relative path or a directory
prefix (anything under it is in scope). A changed path matching no intended
entry is reported as OUT-OF-SCOPE — a candidate for exclusion from the commit
(e.g. via `git restore --staged <path>`, which YOU run after reviewing).
"""
import subprocess
import sys
from pathlib import Path


def _repo_root() -> str:
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        print("not a git repository (git rev-parse failed)", file=sys.stderr)
        sys.exit(0)  # advisory: never hard-fail
    return p.stdout.strip()


def _changed_paths(root: str) -> list[tuple[str, str]]:
    """Return (status_code, path) for every changed path, staged or unstaged.
    Renames report the destination path."""
    p = subprocess.run(["git", "-C", root, "status", "--porcelain=v1"],
                       capture_output=True, text=True)
    out = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        code, rest = line[:2], line[3:]
        if " -> " in rest:  # rename/copy: take the destination
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        out.append((code, rest))
    return out


def _in_scope(path: str, intended: list[str]) -> bool:
    for want in intended:
        w = want.rstrip("/")
        if path == w or path.startswith(w + "/"):
            return True
    return False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: guard.py <intended-path-or-prefix> [<intended...>]", file=sys.stderr)
        return 0
    intended = [a.strip() for a in argv if a.strip()]
    root = _repo_root()
    changed = _changed_paths(root)

    in_scope = [(c, p) for c, p in changed if _in_scope(p, intended)]
    out_scope = [(c, p) for c, p in changed if not _in_scope(p, intended)]

    print("commit-scope-guard — ADVISORY, read-only (nothing was staged or restored)")
    print(f"intended scope: {', '.join(intended)}")
    print()
    print(f"IN-SCOPE ({len(in_scope)}):")
    for c, p in in_scope:
        print(f"  [{c}] {p}")
    print()
    print(f"OUT-OF-SCOPE ({len(out_scope)}) — review before committing:")
    for c, p in out_scope:
        staged = c[0] not in " ?"  # index column non-blank/non-untracked = staged
        hint = "  (staged — `git restore --staged` to drop it)" if staged else ""
        print(f"  [{c}] {p}{hint}")
    print()
    if out_scope:
        print(f"VERDICT: {len(out_scope)} out-of-scope change(s) — decide per file "
              "whether to exclude from this cycle's commit. Nothing was changed for you.")
    else:
        print("VERDICT: CLEAN — every changed path is within the intended scope.")
    return 0  # advisory: always exit 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
