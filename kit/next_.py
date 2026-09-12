#!/usr/bin/env python3
"""next_.py — `kit next`: do the next right thing for the first unfinished ledger row, then stop.

One verb. It is idempotent (run it twice, get the same answer twice) and it always stops at the
next *human* gate rather than guessing past it. The six states below are the whole product:

    no fixtures   -> tell the orchestrator what to capture, from both systems
    no packet     -> scaffold it from the template and list the blanks to fill
    blanks left   -> list them and refuse to spend
    not executed  -> worktree -> implementer -> gates -> verifier   (the only paid step)
    not verified  -> print the orchestrator's six verification steps
    verified      -> commit and tag on the task branch

Nothing here is clever. That is the point: the judgement lives in the packet and in the human.
"""
import json, sys
from pathlib import Path

from . import ledger
from .campaign import (draft_packet, ensure_gates, newest_campaign, packet_state, say, die,
                       repo_root, sh)
from .unit import run_unit
from .accept import cmd_accept

BLANK = ("<", ">")


def blanks(packet: Path):
    """The `<…>` spots a human still owes. Angle-bracket placeholders only; paths and code are safe."""
    import re
    out = []
    for line in packet.read_text().splitlines():
        if re.search(r"<[a-z][^>`]{2,}>", line) and not line.lstrip().startswith(("- `", "`")):
            out.append(line.strip())
    return out


def fixture_paths(campaign: Path, row_id: str):
    return (campaign / "fixtures" / "oracle" / f"{row_id}.md",
            campaign / "fixtures" / "subject" / f"{row_id}.md")


def _meta(campaign: Path):
    cfg = campaign / "config.json"
    return json.loads(cfg.read_text()) if cfg.is_file() else {}


def cmd_next(campaign_arg=None, harness=None, row_arg=None, run=True):
    repo = repo_root() or die("not inside a git repository")
    campaign = Path(campaign_arg).resolve() if campaign_arg else newest_campaign(repo, None)
    if campaign is None or not (campaign / "config.json").is_file():
        die('no campaign here. Start one with:\n  kit init <slug> --oracle "<reference>" --subject "<ours>"')
    cfg = _meta(campaign)
    rows = ledger.rows(campaign)
    row = next((r for r in rows if r["id"] == row_arg), None) if row_arg else ledger.next_open(campaign)
    say(f"kit next: {campaign.relative_to(repo)}")
    if row is None:
        done = sum(1 for r in rows if r["verdict"] in ("PASS", "SKIP"))
        if not rows:
            say('  ledger is empty. Add what you can observe:\n    kit ledger add "<one observable behaviour>"')
            return 0
        say(f"  ledger is green: {done}/{len(rows)} rows PASS or SKIP. Nothing to do.")
        return 0

    rid = row["id"]
    say(f"  row {rid}: {row['behaviour'][:80]}   [{row['verdict']}]")
    oracle, subject = fixture_paths(campaign, rid)
    packet = campaign / "packets" / f"{rid}.md"
    receipt = campaign / "receipts" / f"{rid}-receipt.md"
    live = campaign / "receipts" / f"{rid}-live.md"

    # 1 — fixtures. The orchestrator drives both systems; no model ever sees them.
    if not oracle.is_file() or not subject.is_file():
        say("\n  STATE: fixtures missing. This step is yours — models never open a browser.")
        say(f"    oracle  {'ok' if oracle.is_file() else 'MISSING'}  {oracle.relative_to(repo)}")
        say(f"    subject {'ok' if subject.is_file() else 'MISSING'}  {subject.relative_to(repo)}")
        say(f"\n  Oracle:  {cfg.get('oracle', '<not set>')}")
        say(f"  Subject: {cfg.get('subject', '<not set>')}")
        say("\n  Capture measured values, never impressions: computed styles, DOM counts, element")
        say("  geometry before and after. Observe-only on the oracle: no sends, publishes or saves.")
        say(f"\n  Then run `kit next` again.")
        return 2

    # 2 — packet. Drafted locally in zero seconds for zero dollars; a model must never author one.
    if not packet.is_file():
        gates_doc = ensure_gates(campaign, repo, measure=False)
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(draft_packet(rid, row["behaviour"], str(oracle.relative_to(repo)),
                                       cfg.get("default_files", ""), gates_doc, campaign, repo))
        say(f"\n  STATE: packet drafted (0s, $0) — {packet.relative_to(repo)}")
        say("  Fill the blanks below. Precision here IS the cost control: a precise packet costs")
        say("  $0.05 and lands first time; a vague one cost $1.03 and produced broken output.")
        for b in blanks(packet):
            say(f"    {b[:110]}")
        return 2
    left = blanks(packet)
    if left:
        say(f"\n  STATE: packet has {len(left)} blank(s) — {packet.relative_to(repo)}")
        for b in left:
            say(f"    {b[:110]}")
        say("\n  Fill them, then `kit next`. Nothing is spent until the packet is complete.")
        return 2

    # 3 — execute. The only step that spends money.
    if not receipt.is_file():
        if not run:
            say(f"\n  STATE: ready to execute. `kit next` would run the unit now.")
            return 2
        say(f"\n  STATE: executing — worktree, implementer, gates, verifier")
        name = row["behaviour"][:70]
        prev = next((r["unit"] for r in reversed(ledger.rows(campaign))
                     if r["verdict"] == "PASS" and r["unit"] and r["id"] != rid), None)
        rc = run_unit(repo, campaign, packet, rid, name, last=False, prev_unit=prev or None)
        if not receipt.is_file():
            say("\n  The verifier wrote no receipt. Read the run log named above before re-running;")
            say("  a timeout means the packet was wrong, not the prompt.")
            return rc or 1

    # 4 — verification. The orchestrator's job, and the reason false greens never shipped.
    if not live.is_file():
        verdict = receipt.read_text().splitlines()[0].strip() if receipt.read_text().strip() else "(empty)"
        say(f"\n  STATE: executed, not verified. The verifier said: {verdict}")
        say("  A model's ACCEPT is a claim. Four of nine units on 2026-09-10 had a green receipt and")
        say("  a broken live page. Close it yourself, in this order:")
        say(f"    1. gate record   {(campaign / f'gates-run-{rid}.json').relative_to(repo)}")
        say(f"    2. the diff      {(campaign / 'receipts' / (rid + '.diff')).relative_to(repo)}  — every path must be in packet §2")
        say(f"    3. the test      read it; would it pass without the change?")
        say(f"    4. mutation test cp the file aside, break the change, the §5 test must go RED, restore byte-identical")
        say(f"    5. live check    open the subject and confirm the behaviour with your own eyes")
        say(f"    6. write         {live.relative_to(repo)}   first line `LIVE: PASS`, then `evidence:` lines")
        say("\n  Then `kit next` commits and tags it.")
        return 2

    # 5 — accept.
    say(f"\n  STATE: verified. Committing and tagging.")
    rc = cmd_accept(rid, str(campaign))
    if rc == 0:
        ledger.set_verdict(campaign, rid, "PASS", unit=rid, gate="live")
        say(f"  ledger: {rid} -> PASS")
        nxt = ledger.next_open(campaign)
        say(f"\n  Next row: {nxt['id']} — {nxt['behaviour'][:70]}" if nxt else "\n  Ledger is green.")
    return rc
