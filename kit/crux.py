#!/usr/bin/env python3
"""crux.py — optional hand-off into crux's organisation. Advisory, never on the critical path.

The kit writes only through crux's documented front door: a note in `<docs_dir>/inbox/` that
`process-inbox` classifies and files (COMPAT rule 5 — never into the tree itself). If the repo has
no crux tree, the kit says so once and carries on: a unit must never pay for a docs bootstrap
(measured 2026-09-11: 3.5 minutes of `init-docs` in front of a 105-second worker).
"""
import json, subprocess, time
from pathlib import Path

HOME = Path.home()
_ROOTS = [HOME / ".cache" / "omnitech-dev-kit" / "crux" / "crux",
          *sorted((HOME / ".claude" / "plugins" / "cache" / "crux" / "crux").glob("*"), reverse=True)]


def docs_dir(repo: Path):
    """Ask crux's own resolver where the tree is; never guess. None when crux or the tree is absent."""
    root = next((r for r in _ROOTS if (r / "scripts" / "bionic-config.py").is_file()), None)
    if root:
        r = subprocess.run(["uv", "run", str(root / "scripts" / "bionic-config.py"), "--repo-root", str(repo)],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                d = Path(json.loads(r.stdout)["docs_root"])
                return d if (d / "manifest.yml").is_file() else None
            except (ValueError, KeyError):
                pass
    for name in ("bionic", "docs"):
        d = repo / name
        if (d / "manifest.yml").is_file() and (d / "inbox").is_dir():
            return d
    return None


def inbox_drop(repo: Path, slug: str, title: str, body: str, enabled=True):
    """One note for process-inbox. Returns the path, or None when there is nothing to write into."""
    if not enabled:
        return None
    d = docs_dir(repo)
    if not d:
        return None
    inbox = d / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    f = inbox / f"{time.strftime('%Y-%m-%d')}-kit-{slug}.md"
    f.write_text(f"# {title}\n\n_Dropped by omnitech-dev-kit {time.strftime('%Y-%m-%d %H:%M')}; "
                 f"file with process-inbox._\n\n{body.rstrip()}\n")
    return f


def crux_inbox_drop(repo: Path, slug_: str, title: str, body: str):
    """Name kept for the call sites in unit.py and accept.py. Failure here never fails a unit."""
    try:
        f = inbox_drop(repo, slug_, title, body)
    except OSError:
        return None
    if f:
        print(f"  crux: dropped {f.relative_to(repo)} for process-inbox", flush=True)
    return f
