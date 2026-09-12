#!/usr/bin/env python3
"""home.py — the machine layer: "has today got away from me?", across every repo and campaign.

A campaign folder answers "what is this piece of work?". It cannot answer the question that
actually costs money, because spend.jsonl is per campaign: two campaigns in one session each got
their own budget and the session cap silently did not bind (found by audit, 2026-09-12 — the same
class of bug as a swallowed import).

    $KIT_HOME  (default ~/.desoleary/omnitech-dev-kit/)
      config.{yaml,json}        machine defaults and rules
      sessions/<session>.jsonl  every run, across every repo and campaign
      campaigns.jsonl           index: repo · campaign · last activity · spend
      HALTED.json               machine-level halt: stops every campaign, everywhere

A session is a property of *you*, not of a directory: orchestrators run concurrently across
workspaces, and "today" spans all of them. Per-workspace budgets belong in config rules
(`when: {repo: {glob: "legion-*"}}`), which survive a repo moving; a directory does not.

Both ledgers are append-only JSONL, so concurrent orchestrators need no lock: a single small
append is atomic on every filesystem we target, and the index is rebuildable by scanning.
"""
import json, os, time
from pathlib import Path


def home() -> Path:
    d = Path(os.environ.get("KIT_HOME", "~/.desoleary/omnitech-dev-kit")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_id() -> str:
    """Explicit `KIT_SESSION_ID` when set; otherwise one session per day.

    Per-day is the right default: the question the session cap exists to answer is "has today got
    away from me?", and an orchestrator that forgets to set a session id must not thereby escape
    the cap. Opting *out* of grouping should be deliberate, never accidental.
    """
    return os.environ.get("KIT_SESSION_ID") or f"auto-{time.strftime('%Y%m%d')}"


def session_file(sid: str = None) -> Path:
    d = home() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sid or session_id()}.jsonl"


def record(row: dict, repo: Path = None, campaign: Path = None):
    """Append one run to the session ledger and touch the campaign index. Never raises."""
    try:
        entry = dict(row)
        entry["session"] = row.get("session") or session_id()
        entry["repo"] = str(repo) if repo else None
        entry["campaign_path"] = str(campaign) if campaign else None
        with open(session_file(entry["session"]), "a") as f:
            f.write(json.dumps(entry) + "\n")
        if campaign:
            with open(home() / "campaigns.jsonl", "a") as f:
                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "repo": str(repo) if repo else None,
                                    "campaign": str(campaign), "unit": row.get("unit"),
                                    "role": row.get("role"), "cost_usd": row.get("cost_usd"),
                                    "seconds": row.get("seconds"), "exit": row.get("exit")}) + "\n")
    except OSError:
        pass


def rows(sid: str = None):
    f = session_file(sid)
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


def spent(sid: str = None, since_day: str = None) -> float:
    """Dollars in this session, or across all sessions for one day."""
    if since_day:
        total = 0.0
        d = home() / "sessions"
        for f in (d.glob("*.jsonl") if d.is_dir() else []):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if str(r.get("ts", ""))[:8] == since_day:
                    total += float(r.get("cost_usd") or 0)
        return total
    return sum(float(r.get("cost_usd") or 0) for r in rows(sid))


def halt_file() -> Path:
    return home() / "HALTED.json"


def halt(reasons, context: dict = None):
    halt_file().write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": session_id(),
        "reasons": list(reasons), **(context or {}),
        "clear_with": "kit resume --machine",
    }, indent=2) + "\n")


def halted():
    f = halt_file()
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except ValueError:
        return {"reasons": ["HALTED.json at $KIT_HOME is unreadable; delete it deliberately"]}


def campaigns():
    """The index, newest activity per campaign."""
    f = home() / "campaigns.jsonl"
    if not f.is_file():
        return {}
    seen = {}
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        c = r.get("campaign")
        if not c:
            continue
        agg = seen.setdefault(c, {"repo": r.get("repo"), "runs": 0, "usd": 0.0, "at": r.get("at")})
        agg["runs"] += 1
        agg["usd"] += float(r.get("cost_usd") or 0)
        agg["at"] = max(agg["at"] or "", r.get("at") or "")
    return seen
