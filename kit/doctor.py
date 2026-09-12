#!/usr/bin/env python3
"""doctor.py — advisory only. It reports; it never blocks a unit (law 4)."""
import json, os, shutil, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent


def cmd_doctor():
    ok = True
    print(f"kit {KIT}")
    print(f"  python      {sys.version.split()[0]}")
    for h in ("omp", "claude", "codex", "opencode"):
        exe = shutil.which(h)
        adapter = (KIT / "harness" / f"{h}.sh").is_file()
        print(f"  harness {h:9s} {'found' if exe else 'not installed':13s} adapter {'yes' if adapter else 'NO'}")
    key = os.environ.get("OPENROUTER_API_KEY")
    print(f"  OPENROUTER_API_KEY  {'set' if key else 'NOT SET — metered runs will refuse'}")
    from .campaign import repo_root
    repo = repo_root()
    if repo:
        camps = sorted((repo / ".kit").glob("*/config.json")) if (repo / ".kit").is_dir() else []
        print(f"  repo        {repo}")
        print(f"  campaigns   {len(camps)}" + (f" ({', '.join(c.parent.name for c in camps)})" if camps else ""))
        from .crux import docs_dir
        d = docs_dir(repo)
        print(f"  crux tree   {d.relative_to(repo) if d else 'none (optional — notes stay in the campaign)'}")
    print("\nadvisory only: nothing here stops a unit.")
    return 0 if ok else 0
