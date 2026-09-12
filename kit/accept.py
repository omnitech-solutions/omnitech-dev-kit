#!/usr/bin/env python3
"""accept.py - the orchestrator has verified it; commit and tag on the task branch."""
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


from .crux import crux_inbox_drop
from .campaign import gate_lines_from, newest_campaign, owned_paths


def cmd_accept(unit, campaign_arg):
    """Commit an already-verified unit's worktree on its task branch, tag it, file the journal note.
    The human read the diff; this only refuses to bless what the gate record and receipts don't support."""
    repo = repo_root() or die("not inside a git repository")
    campaign = newest_campaign(repo, campaign_arg) or die("no campaign found; run `kit do` or `kit unit` once", 2)
    packet = campaign / "packets" / f"{unit}.md"
    if not packet.is_file():
        die(f"no packet {unit}.md in {campaign}", 2)
    receipt = campaign / "receipts" / f"{unit}-receipt.md"
    verdict = (receipt.read_text().strip().splitlines() or [""])[0].strip() if receipt.is_file() else ""
    if verdict != "VERDICT: ACCEPT":
        die(f"{receipt.name} does not start with 'VERDICT: ACCEPT' ({verdict or 'missing'}) — nothing is accepted", 2)
    try:
        gates_doc = json.loads((campaign / "gates.json").read_text())
    except (OSError, ValueError):
        gates_doc = {"gates": []}
    # The live gate is on unless the campaign turns it off. It fires from config.json's `live_gate`
    # (what `kit init` writes) or from any gate declared `kind: live`. Default ON: a campaign that
    # forgot to declare one must not silently lose the only gate a model cannot fake.
    try:
        cfg_doc = json.loads((campaign / "config.json").read_text())
    except (OSError, ValueError):
        cfg_doc = {}
    live_required = cfg_doc.get("live_gate", True) or any(
        g.get("kind") == "live" for g in gates_doc.get("gates", []))
    if live_required:
        live = campaign / "receipts" / f"{unit}-live.md"
        lines = live.read_text().splitlines() if live.is_file() else []
        evidence = next((l[len("evidence:"):].strip() for l in lines if l.startswith("evidence:")), "")
        # a DOM measurement is text; a screenshot path must exist (worktree- or repo-relative, or absolute)
        if evidence and not Path(evidence).is_file() and not (repo / evidence).is_file() \
                and not (repo.parent / f"wt-{campaign.name}-{unit}" / evidence).is_file() and " " not in evidence:
            evidence = ""  # names a file that does not exist: not evidence
        if not (lines and lines[0].strip() == "LIVE: PASS" and evidence):
            die(f"this campaign has a live gate: {live.name} must exist, start with 'LIVE: PASS' and carry an "
                f"'evidence:' line (a screenshot path that exists, or a DOM measurement) — nothing is accepted "
                f"without a human-checked live result", 6)
    wt = repo.parent / f"wt-{campaign.name}-{unit}"
    if not wt.is_dir():
        die(f"no worktree {wt} for unit {unit}", 2)
    owned = owned_paths(packet)
    dirty = [l[3:].strip().strip('"') for l in
             sh(["git", "-C", str(wt), "status", "--porcelain"]).stdout.splitlines() if l[3:].strip()]
    breach = [p for p in (d.split(" -> ")[-1] for d in dirty)
              if p not in owned and not any(p.startswith(o.rstrip("/") + "/") for o in owned)]
    if breach:
        die("the worktree's diff touches files outside the packet's owned files: "
            + ", ".join(breach) + " — resolve it by hand, do not force this", 4)
    gate_lines = gate_lines_from(campaign / f"gates-run-{unit}.json")
    title = (packet.read_text().splitlines() or [""])[0].lstrip("# ").strip()
    agents = campaign / f"AGENTS-{slug(campaign.name, 24)}.md"
    trailer = next((l for l in agents.read_text().splitlines() if l.startswith("Co-Authored-By:")), "") \
        if agents.is_file() else ""
    msg = f"{title}\n\nPacket {unit}. Gates: {'; '.join(gate_lines) if gate_lines else 'none recorded'}. Verifier ACCEPT."
    if trailer:
        msg += f"\n\n{trailer}"
    sh(["git", "-C", str(wt), "add", "-A"])
    c = subprocess.run(["git", "-C", str(wt), "-c", "user.name=kit", "-c", "user.email=kit@local",
                        "commit", "-q", "-F", "-"], input=msg, text=True, capture_output=True)
    if c.returncode != 0:
        die(f"commit failed: {c.stderr.strip()[:300]}", 3)
    tag = f"kit/{campaign.name}-{unit.lower()}-after"
    sh(["git", "-C", str(wt), "tag", "-f", tag])
    branch = sh(["git", "-C", str(wt), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    head = sh(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"]).stdout.strip()
    say(f"  accepted: committed on {branch} @ {head} and tagged {tag}")
    gr = campaign / f"gates-run-{unit}.json"
    crux_inbox_drop(repo, f"{campaign.name[:24]}-{unit.lower()}", f"kit unit {unit}: {title}",
        f"kind: journal\ncampaign: {campaign.name}\nunit: {unit}\npacket: {packet.relative_to(repo)}\n"
        f"receipt: {receipt.relative_to(repo)}\n"
        f"gates: {gr.relative_to(repo) if gr.is_file() else '-'}\n"
        f"branch: {branch} @ {head}   tag: {tag}\n"
        f"verdict: VERDICT: ACCEPT\n\nWhat changed: {title}. Evidence: the receipt and gate record; the diff is `git show {head}`.")
    return 0
