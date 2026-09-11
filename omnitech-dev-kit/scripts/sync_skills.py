#!/usr/bin/env python3
"""sync_skills.py — mirror kit skills into machine-local live skill directories, with a receipt.

usage: sync_skills.py [--target DIR ...] [--dry-run]
Default targets: $PI_CODING_AGENT_DIR/skills (omp, default ~/.omp/agent/skills).
Direction is kit → targets only (the kit is the source of truth; edit skills in the kit, then sync).
Safety:
- ownership manifest: every directory this script installs is recorded in <target>/.kit-owned.json. A
  destination that exists but is NOT in the manifest is treated as someone else's skill and is REFUSED,
  not overwritten, even when the names match. Use --adopt to claim it deliberately.
- recursive comparison: a change in any nested file counts as a difference (a top-level compare missed
  edits inside subdirectories and reported them as unchanged).
- --dry-run touches nothing at all, including creating the target directory.
- refuses a target that is not a directory; never deletes anything it does not own.
"""
import hashlib, json, os, shutil, sys
from pathlib import Path

MANIFEST = ".kit-owned.json"

def tree_digest(d: Path) -> str:
    """Content hash of an entire skill directory, so nested edits are never reported as unchanged."""
    h = hashlib.sha256()
    for f in sorted(x for x in d.rglob("*") if x.is_file() and x.name not in (".DS_Store",)):
        h.update(str(f.relative_to(d)).encode()); h.update(f.read_bytes())
    return h.hexdigest()

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
    adopt = "--adopt" in a
    targets = [Path(a[i + 1]).expanduser() for i, x in enumerate(a) if x == "--target"]
    if not targets:
        targets = [Path(os.environ.get("PI_CODING_AGENT_DIR", "~/.omp/agent")).expanduser() / "skills"]
    skills = skill_dirs()
    for t in targets:
        if t.exists() and not t.is_dir(): print(f"refuse: {t} is not a directory", file=sys.stderr); sys.exit(1)
        if not dry: t.mkdir(parents=True, exist_ok=True)
        mf = t / MANIFEST
        owned = json.loads(mf.read_text()).get("owned", {}) if mf.is_file() else {}
        added = updated = same = 0
        refused = []
        for s in skills:
            dest = t / s.name
            digest = tree_digest(s)
            if dest.exists():
                if s.name not in owned and not adopt:
                    refused.append(s.name); continue
                if tree_digest(dest) == digest: same += 1; owned[s.name] = digest; continue
                updated += 1
                if not dry: shutil.rmtree(dest); shutil.copytree(s, dest, ignore=EXCL)
            else:
                added += 1
                if not dry: shutil.copytree(s, dest, ignore=EXCL)
            owned[s.name] = digest
        if not dry:
            mf.write_text(json.dumps({"owned": owned, "source": str(KIT)}, indent=2) + "\n")
        print(f"receipt: target={t} skills={len(skills)} added={added} updated={updated} unchanged={same}"
              f"{f' refused={len(refused)}' if refused else ''}{' (dry-run)' if dry else ''}")
        for r in refused:
            print(f"  REFUSED {r}: exists at {t/r} and is not in {MANIFEST}. It may be your own skill with "
                  f"the same name. Inspect it, then re-run with --adopt to let the kit manage it.", file=sys.stderr)
        if refused: sys.exit(2)

if __name__ == "__main__":
    main(sys.argv[1:])
