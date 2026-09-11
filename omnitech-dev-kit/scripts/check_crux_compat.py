#!/usr/bin/env python3
"""check_crux_compat.py — enforce COMPAT.md against the installed crux (stdlib only).

usage: check_crux_compat.py [--crux-root DIR]
Locates crux via --crux-root, $CRUX_PLUGIN_ROOT, or the Claude Code plugin cache; then checks:
  1. crux version >= plugin.json requires.crux
  2. no kit skill id collides with a crux catalog id
  3. crux forge-skill still carries the seven-event enum string and the evaluated exemplar the kit relies on
  4. kit skills carry the runtime-compat block verbatim from crux
exit 0 ok, 1 incompatibility (details on stderr), 2 crux not found
"""
import json, os, re, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
ENUM = "authored | revised | used | evaluated | fallback | escalated | pruned"
EXEMPLAR = "- verdict: effective | gap: closed | recommend: keep"

def find_crux(arg):
    cands = []
    if arg: cands.append(Path(arg))
    if os.environ.get("CRUX_PLUGIN_ROOT"): cands.append(Path(os.environ["CRUX_PLUGIN_ROOT"]))
    cache = Path.home() / ".claude" / "plugins"
    if cache.is_dir():
        cands += [p.parent for p in cache.rglob("plugin.json") if p.parent.name == "crux" or (p.parent / "catalog" / "skills.json").exists()]
    for c in cands:
        if (c / "plugin.json").is_file() and (c / "catalog" / "skills.json").is_file(): return c
    return None

def vtuple(v): return tuple(int(x) for x in re.findall(r"\d+", v)[:3])

def main(a):
    root = find_crux(a[a.index("--crux-root") + 1] if "--crux-root" in a else None)
    if not root: print("crux not found (pass --crux-root or set CRUX_PLUGIN_ROOT)", file=sys.stderr); sys.exit(2)
    errs = []
    crux = json.loads((root / "plugin.json").read_text())
    kit = json.loads((KIT / "plugin.json").read_text())
    floor = kit.get("requires", {}).get("crux", ">=0").lstrip(">=")
    if vtuple(crux["version"]) < vtuple(floor): errs.append(f"crux {crux['version']} < required {floor}")
    crux_ids = {x["id"] for x in json.loads((root / "catalog" / "skills.json").read_text())}
    kit_ids = {Path(s).parent.name for s in kit["skills"]}
    for c in sorted(kit_ids & crux_ids): errs.append(f"skill id collision with crux: {c}")
    for k in sorted(kit_ids):
        if not k.startswith("kit-"): errs.append(f"kit skill not namespaced: {k}")
    forge = root / "skills" / "forge-skill" / "SKILL.md"
    if forge.is_file():
        t = forge.read_text()
        if ENUM not in t: errs.append("crux forge-skill no longer carries the seven-event enum the kit forge-log depends on")
        if EXEMPLAR not in t: errs.append("crux forge-skill no longer carries the evaluated exemplar")
        m = re.search(r"<!-- BEGIN GENERATED: runtime-compat -->.*?<!-- END GENERATED: runtime-compat -->", t, re.S)
        if m:
            block = m.group(0)
            for s in kit["skills"]:
                st = (KIT / s).read_text()
                if block not in st: errs.append(f"runtime-compat block drifted from crux in {s}")
    else:
        errs.append("crux forge-skill/SKILL.md missing")
    for e in errs: print(f"INCOMPATIBLE: {e}", file=sys.stderr)
    print(f"crux {crux['version']} at {root}: {'INCOMPATIBLE' if errs else 'COMPATIBLE'} ({len(kit_ids)} kit skills, {len(crux_ids)} crux skills)")
    sys.exit(1 if errs else 0)

if __name__ == "__main__":
    main(sys.argv[1:])
