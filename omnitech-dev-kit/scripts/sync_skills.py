#!/usr/bin/env python3
"""sync_skills.py — mirror kit skills into machine-local live skill directories, with a receipt.

usage: sync_skills.py [--target DIR ...] [--dry-run]
Default targets: $PI_CODING_AGENT_DIR/skills (omp, default ~/.omp/agent/skills).
Direction is kit → targets only (the kit is the source of truth; edit skills in the kit, then sync).
Safety: only replaces target dirs whose name starts with 'kit-' or that live under a 'borrowed/' folder
copied by this script; never deletes anything else; refuses a target that is not a directory.
"""
import filecmp, os, shutil, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SRC = KIT / "skills"
EXCL = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc")

def skill_dirs():
    out = []
    for d in sorted(SRC.iterdir()):
        if d.name == "borrowed":
            out += [x for x in sorted(d.iterdir()) if (x / "SKILL.md").is_file()]
        elif (d / "SKILL.md").is_file():
            out.append(d)
    return out

def main(a):
    dry = "--dry-run" in a
    targets = [Path(a[i + 1]).expanduser() for i, x in enumerate(a) if x == "--target"]
    if not targets:
        targets = [Path(os.environ.get("PI_CODING_AGENT_DIR", "~/.omp/agent")).expanduser() / "skills"]
    skills = skill_dirs()
    for t in targets:
        if t.exists() and not t.is_dir(): print(f"refuse: {t} is not a directory", file=sys.stderr); sys.exit(1)
        t.mkdir(parents=True, exist_ok=True)
        added = updated = same = 0
        for s in skills:
            dest = t / s.name
            if dest.exists():
                cmp = filecmp.dircmp(s, dest)
                if not (cmp.left_only or cmp.right_only or cmp.diff_files): same += 1; continue
                updated += 1
                if not dry: shutil.rmtree(dest); shutil.copytree(s, dest, ignore=EXCL)
            else:
                added += 1
                if not dry: shutil.copytree(s, dest, ignore=EXCL)
        print(f"receipt: target={t} skills={len(skills)} added={added} updated={updated} unchanged={same}{' (dry-run)' if dry else ''}")

if __name__ == "__main__":
    main(sys.argv[1:])
