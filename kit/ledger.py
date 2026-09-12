#!/usr/bin/env python3
"""ledger.py — one row per observable difference, in a markdown table a human can edit.

The ledger is the campaign's only work queue. `kit next` walks it top to bottom and stops at the
first row that is not PASS. Nothing else decides what to work on — not the tool, not a model.
"""
import re
from pathlib import Path

HEADER = "| id | behaviour | oracle | subject | verdict | unit | gate |"
RULE = "|----|-----------|--------|---------|---------|------|------|"
VERDICTS = ("OPEN", "FAIL", "PARTIAL", "PASS", "SKIP")


def path(campaign: Path) -> Path:
    return campaign / "ledger.md"


def template(slug: str, oracle: str, subject: str) -> str:
    return f"""# Ledger — {slug}

**Oracle:** {oracle}
**Subject:** {subject}

One row per *observable* behaviour — something you can point at in both systems and measure.
Verdicts: OPEN (not started) · FAIL (reproduced) · PARTIAL · PASS (accepted) · SKIP (deliberate divergence).
`kit next` works the first row that is not PASS or SKIP. Edit this file by hand whenever you like.

{HEADER}
{RULE}
"""


def rows(campaign: Path):
    f = path(campaign)
    if not f.is_file():
        return []
    out = []
    for n, line in enumerate(f.read_text().splitlines(), 1):
        if not line.startswith("|") or line.startswith(("|----", "| id ")):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0]:
            continue
        cells += [""] * (7 - len(cells))
        out.append({"line": n, "id": cells[0], "behaviour": cells[1], "oracle": cells[2],
                    "subject": cells[3], "verdict": (cells[4] or "OPEN").upper(),
                    "unit": cells[5], "gate": cells[6]})
    return out


def add(campaign: Path, behaviour: str, row_id=None) -> dict:
    existing = rows(campaign)
    if row_id is None:
        nums = [int(m.group(1)) for r in existing if (m := re.search(r"(\d+)$", r["id"]))]
        prefix = existing[0]["id"].rstrip("0123456789") if existing else "R-"
        row_id = f"{prefix}{max(nums, default=0) + 1:02d}"
    if any(r["id"] == row_id for r in existing):
        raise ValueError(f"row {row_id} already exists")
    f = path(campaign)
    text = f.read_text().rstrip("\n")
    text += f"\n| {row_id} | {behaviour} | - | - | OPEN | - | - |\n"
    f.write_text(text)
    return {"id": row_id, "behaviour": behaviour, "verdict": "OPEN"}


def set_verdict(campaign: Path, row_id: str, verdict: str, unit="", gate=""):
    f = path(campaign)
    out = []
    for line in f.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 5 and cells[0] == row_id:
            cells += [""] * (7 - len(cells))
            cells[4] = verdict
            if unit:
                cells[5] = unit
            if gate:
                cells[6] = gate
            line = "| " + " | ".join(cells[:7]) + " |"
        out.append(line)
    f.write_text("\n".join(out) + "\n")


def next_open(campaign: Path):
    """The first row that still owes work. None when the ledger is green."""
    return next((r for r in rows(campaign) if r["verdict"] not in ("PASS", "SKIP")), None)
