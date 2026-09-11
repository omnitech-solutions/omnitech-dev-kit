#!/usr/bin/env python3
"""validate.py — fail-closed shape checks for kit artefacts (stdlib only).

usage: validate.py packet <file> [--repo DIR]   # 8 sections in order, ≤120 lines, §2 paths exist under --repo
       validate.py receipt <file>               # first line VERDICT: ACCEPT|REJECT, ≥1 gate line, ≤80 lines
       validate.py forge-log <file>             # every header matches crux's locked regex; evaluated entries carry the 2-line exemplar
       validate.py spend <file.jsonl>           # each line has the required keys
exit 0 = valid, 1 = invalid (reasons on stderr), 2 = usage
"""
import json, re, sys
from pathlib import Path

SECTIONS = ["## 1. Protected inputs", "## 2. Owned files", "## 3. Todo DAG", "## 4. Structural evidence",
            "## 5. Real-boundary test", "## 6. Definition of done", "## 7. Checkpoint", "## 8. Out of scope"]
GATE = re.compile(r"^gate: .+ \(.+\) → exit \d+ — .+$")
FORGE_HDR = re.compile(r"^## \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] (authored|revised|used|evaluated|fallback|escalated|pruned) \| [a-z0-9][a-z0-9-]*$")
EVAL1 = re.compile(r"^- verdict: (effective|fell-short|mixed) \| gap: (closed|partial|not-closed) \| recommend: (keep|revise|prune)$")
SPEND_KEYS = {"ts", "role", "unit", "seconds", "exit", "cost_usd", "cumulative_usd", "log"}

def packet(path, repo):
    text = Path(path).read_text().splitlines(); errs = []
    if len(text) > 120: errs.append(f"{len(text)} lines > 120")
    pos = -1
    for s in SECTIONS:
        idx = next((i for i, l in enumerate(text) if l.startswith(s)), None)
        if idx is None: errs.append(f"missing section {s!r}")
        elif idx < pos: errs.append(f"section out of order {s!r}")
        else: pos = idx
    if repo:
        i2 = next((i for i, l in enumerate(text) if l.startswith(SECTIONS[1])), None)
        i3 = next((i for i, l in enumerate(text) if l.startswith(SECTIONS[2])), len(text))
        if i2 is not None:
            for l in text[i2 + 1:i3]:
                m = re.match(r"^- `([^`]+)`", l)
                if m and not (Path(repo) / m.group(1)).exists() and "NEW" not in l:
                    errs.append(f"owned file does not exist (mark NEW if intended): {m.group(1)}")
    return errs

def receipt(path):
    text = Path(path).read_text().splitlines(); errs = []
    if not text or text[0] not in ("VERDICT: ACCEPT", "VERDICT: REJECT"): errs.append("first line must be 'VERDICT: ACCEPT' or 'VERDICT: REJECT'")
    if not any(GATE.match(l.strip("- ").strip()) for l in text): errs.append("no gate line in the form 'gate: <cmd> (<dir>) → exit N — <token>'")
    if len(text) > 80: errs.append(f"{len(text)} lines > 80")
    return errs

def forge_log(path):
    text = Path(path).read_text().splitlines(); errs = []
    for i, l in enumerate(text):
        if l.startswith("## ["):
            if not FORGE_HDR.match(l): errs.append(f"line {i+1}: header not in crux locked format: {l}")
            elif "] evaluated |" in l:
                body = [x for x in text[i+1:i+4] if x.strip()]
                if len(body) < 2 or not EVAL1.match(body[0]) or not body[1].startswith("- evidence: "):
                    errs.append(f"line {i+1}: evaluated entry lacks the two-line exemplar")
        elif l.startswith("## ") and not l.startswith("## ["): pass
    return errs

def spend(path):
    errs = []
    for n, l in enumerate(Path(path).read_text().splitlines(), 1):
        if not l.strip(): continue
        try: row = json.loads(l)
        except Exception as e: errs.append(f"line {n}: not JSON ({e})"); continue
        missing = SPEND_KEYS - set(row)
        if missing: errs.append(f"line {n}: missing {sorted(missing)}")
    return errs

def main(a):
    if len(a) < 2: print(__doc__, file=sys.stderr); sys.exit(2)
    kind, f = a[0], a[1]
    repo = a[a.index("--repo") + 1] if "--repo" in a else None
    fn = {"packet": lambda: packet(f, repo), "receipt": lambda: receipt(f), "forge-log": lambda: forge_log(f), "spend": lambda: spend(f)}.get(kind)
    if not fn: print(__doc__, file=sys.stderr); sys.exit(2)
    errs = fn()
    for e in errs: print(f"INVALID {kind} {f}: {e}", file=sys.stderr)
    print(f"{'INVALID' if errs else 'VALID'} {kind} {f}")
    sys.exit(1 if errs else 0)

if __name__ == "__main__":
    main(sys.argv[1:])
