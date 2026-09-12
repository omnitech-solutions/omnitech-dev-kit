#!/usr/bin/env python3
"""status.py - where every campaign is, what it cost, and what is waiting on you."""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HERE = KIT / "kit"


def say(msg=""):
    print(msg, flush=True)


def die(msg, code=2):
    print(f"\nkit: {msg}", file=sys.stderr)
    sys.exit(code)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def repo_root(start=None):
    r = sh(["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"])
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def slug(text, n=48):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n].rstrip("-") or "work")


from .campaign import unit_targets, unit_totals


def cmd_status():
    repo = repo_root() or die("not inside a git repository")
    root = repo / ".desoleary" / "kit"
    camps = sorted(root.glob("*/config.json")) if root.is_dir() else []
    if not camps:
        say("no campaigns yet. Start one with: kit do \"<what you want built>\"")
        return 0
    for cfg in camps:
        c = cfg.parent
        ask = (c / "ASK.md").read_text().splitlines()[-1].strip() if (c / "ASK.md").is_file() else ""
        say(f"\n{c.name}: {ask[:70]}")
        from . import ledger as L
        rows = L.rows(c)
        if rows:
            done = sum(1 for r in rows if r["verdict"] in ("PASS", "SKIP"))
            say(f"  ledger {done}/{len(rows)} green")
            for r in rows:
                if r["verdict"] not in ("PASS", "SKIP"):
                    say(f"    {r['verdict']:8s} {r['id']:8s} {r['behaviour'][:62]}")
        try:
            rows = [json.loads(l) for l in (c / "spend.jsonl").read_text().splitlines() if l.strip()]
        except (OSError, ValueError):
            rows = []
        targets = unit_targets(json.loads(cfg.read_text()))
        for unit, t in sorted(unit_totals(rows).items()):
            over = [k for k, bad in (("usd", t["usd"] > targets["usd"]),
                                     ("time", t["seconds"] > targets["minutes"] * 60)) if bad]
            say(f"  {unit}  ${t['usd']:.2f}  {t['seconds'] // 60}m" + (f" OVER TARGET ({', '.join(over)})" if over else ""))
    return 0
