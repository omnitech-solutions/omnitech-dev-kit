#!/usr/bin/env python3
"""watchdog.py — detect a model getting carried away, and stop it, with nobody watching.

Caps answer "is this over the line?". They cannot answer "is this *unlike* every run before it?",
which is what getting carried away actually looks like. Measured examples from 2026-09-11/12:

    implementer, precise packet      $0.020   172s     <- normal
    implementer, precise packet      $0.032   249s     <- normal
    implementer, vague 12-blank packet $1.03   720s     <- 40x the median, under every cap
    planner, open-ended brief        $0.52    489s     <- produced junk, under every cap

Every one of those was inside the per-run cap. So this compares each run to the trailing median for
its own role and halts on deviation, not just on absolutes.

Two severities, deliberately different:

    WARN   recorded in the row and printed. Never blocks. (A formatting warning once cost three
           runs to an acknowledge gate — that mistake is not repeated here.)
    HALT   writes <campaign>/HALTED.json. `kit next` refuses until a human clears it. Reserved for
           runaway spend, runaway time, and repeated failure on the same unit — the three shapes of
           "it is burning money and not converging".

A halt is a dead-man's switch: it needs no one present to work, and it survives the process.
"""
import json, os, statistics, time
from pathlib import Path

DEFAULTS = {
    "cost_multiple": 4.0,      # this run vs the trailing median for the same role
    "time_multiple": 4.0,
    "min_samples": 3,          # below this there is no baseline; absolutes still apply
    "repeated_failures": 3,    # consecutive non-zero exits on the same unit
    "unit_usd": None,          # falls back to caps.unit_usd
    "enabled": True,
}


def settings_for(settings: dict) -> dict:
    w = dict(DEFAULTS)
    w.update(settings.get("watchdog") or {})
    if w.get("unit_usd") is None:
        w["unit_usd"] = (settings.get("caps") or {}).get("unit_usd")
    return w


def rows_of(spend_dir: Path):
    f = Path(spend_dir) / "spend.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def evaluate(rows, row, w) -> list:
    """Returns [(severity, message)] for the run just recorded. Pure: no I/O, easy to test."""
    if not w.get("enabled", True):
        return []
    out = []
    role, unit = row.get("role"), row.get("unit")
    prior = [r for r in rows if r.get("role") == role and r is not row]

    def deviation(field, key, unit_label, fmt):
        vals = [float(r.get(field) or 0) for r in prior if (r.get(field) or 0) > 0]
        if len(vals) < w["min_samples"]:
            return None
        med = statistics.median(vals)
        cur = float(row.get(field) or 0)
        if med > 0 and cur > med * w[key]:
            return (f"{role} {unit_label} {fmt(cur)} is {cur / med:.1f}x the median of the last "
                    f"{len(vals)} {role} runs ({fmt(med)})")
        return None

    if (m := deviation("cost_usd", "cost_multiple", "cost", lambda v: f"${v:.4f}")):
        out.append(("HALT", m))
    if (m := deviation("seconds", "time_multiple", "wall time", lambda v: f"{int(v)}s")):
        out.append(("WARN", m))

    if w.get("unit_usd"):
        spent = sum(float(r.get("cost_usd") or 0) for r in rows if r.get("unit") == unit)
        if spent > float(w["unit_usd"]):
            out.append(("HALT", f"unit {unit} has spent ${spent:.4f} of its ${float(w['unit_usd']):.2f} "
                                f"budget across all stages"))

    same = [r for r in rows if r.get("unit") == unit][-w["repeated_failures"]:]
    if len(same) >= w["repeated_failures"] and all((r.get("exit") or 0) != 0 for r in same):
        out.append(("HALT", f"unit {unit} has failed {len(same)} times in a row; it is not converging"))

    return out


def halt_file(spend_dir: Path) -> Path:
    return Path(spend_dir) / "HALTED.json"


def check_and_record(spend_dir: Path, row: dict, settings: dict, say=print) -> list:
    """Called right after a spend row is written. Writes HALTED.json when a halt fires."""
    w = settings_for(settings)
    rows = rows_of(spend_dir)
    findings = evaluate(rows, row, w)
    for sev, msg in findings:
        say(f"watchdog: {sev} {msg}")
    halts = [m for s, m in findings if s == "HALT"]
    if halts:
        halt_file(spend_dir).write_text(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "unit": row.get("unit"), "role": row.get("role"), "model": row.get("model"),
            "cost_usd": row.get("cost_usd"), "seconds": row.get("seconds"),
            "session": row.get("session"), "reasons": halts,
            "clear_with": "kit resume   (after you have read the run log and decided)",
        }, indent=2) + "\n")
        say(f"watchdog: HALTED — {halt_file(spend_dir)}")
        say("watchdog: `kit next` will refuse until you read the reason and run `kit resume`.")
        # A hook so a halt can reach you when you are not at the terminal. Config: watchdog.on_halt
        hook = (settings.get("watchdog") or {}).get("on_halt")
        if hook:
            import subprocess
            subprocess.run(hook, shell=True, env={**os.environ,
                                                  "KIT_HALT_REASON": "; ".join(halts),
                                                  "KIT_HALT_UNIT": str(row.get("unit"))})
    return findings


def halted(spend_dir: Path):
    f = halt_file(spend_dir)
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except ValueError:
        return {"reasons": ["HALTED.json is unreadable; delete it deliberately to continue"]}
