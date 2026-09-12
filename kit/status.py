#!/usr/bin/env python3
"""status.py — where every campaign is, what it cost, and what is waiting on you.

This is what to read when you were not here while it ran: the ledger, a cost table per unit against
its targets, and any watchdog halt with the reason it fired.
"""
import json
from pathlib import Path

from .campaign import die, repo_root, say


def _rows(campaign: Path):
    f = campaign / "spend.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def cost_table(campaign: Path, rows):
    """Per unit: runs, dollars, wall time, and whether it beat its targets."""
    from .settings import load as load_settings
    targets = load_settings(campaign)[0].get("targets") or {}
    by = {}
    for r in rows:
        u = by.setdefault(r.get("unit", "?"), {"usd": 0.0, "s": 0, "n": 0, "unknown": 0})
        u["usd"] += float(r.get("cost_usd") or 0)
        u["s"] += int(r.get("seconds") or 0)
        u["n"] += 1
        u["unknown"] += 0 if r.get("cost_known") else 1
    say("")
    say("  unit                      runs      cost     time   vs target")
    total = 0.0
    for unit, v in sorted(by.items()):
        total += v["usd"]
        over = []
        if targets.get("unit_usd") and v["usd"] > float(targets["unit_usd"]):
            over.append("usd")
        if targets.get("unit_minutes") and v["s"] > float(targets["unit_minutes"]) * 60:
            over.append("time")
        flag = "OVER (" + ", ".join(over) + ")" if over else "ok"
        unk = f"   {v['unknown']} unmeasured" if v["unknown"] else ""
        say(f"  {unit[:24]:24s} {v['n']:5d}  ${v['usd']:7.4f}  {v['s'] // 60:3d}m{v['s'] % 60:02d}s   {flag}{unk}")
    say(f"  {'TOTAL':24s} {len(rows):5d}  ${total:7.4f}")
    return total


def cmd_status():
    repo = repo_root() or die("not inside a git repository")
    root = repo / ".desoleary" / "kit"
    camps = sorted(root.glob("*/config.json")) if root.is_dir() else []
    if not camps:
        say('no campaigns yet. Start one with: kit init <slug> --oracle "..." --subject "..."')
        return 0

    from . import ledger as L
    from .watchdog import halted
    grand = 0.0
    for cfg in camps:
        c = cfg.parent
        say(f"\n{c.name}")

        if (h := halted(c)):
            say(f"  ** HALTED **  {h.get('at', '')}  unit {h.get('unit')}")
            for reason in h.get("reasons", []):
                say(f"     {reason}")
            say("     read the run log, then: kit resume")

        rows = L.rows(c)
        if rows:
            done = sum(1 for r in rows if r["verdict"] in ("PASS", "SKIP"))
            say(f"  ledger {done}/{len(rows)} green")
            for r in rows:
                if r["verdict"] not in ("PASS", "SKIP"):
                    say(f"    {r['verdict']:8s} {r['id']:8s} {r['behaviour'][:60]}")

        spend = _rows(c)
        if spend:
            grand += cost_table(c, spend)

    if len(camps) > 1:
        say(f"\nall campaigns: ${grand:.4f}")
    return 0
