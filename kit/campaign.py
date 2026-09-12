#!/usr/bin/env python3
"""campaign.py - a campaign is a folder: config, AGENTS, gates, ledger, packets, receipts."""
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


def ensure_gates(campaign: Path, repo: Path, measure: bool):
    f = campaign / "gates.json"
    if f.is_file():
        return json.loads(f.read_text())
    say("  detecting gates from the repository…" + (" (measuring baselines, this takes a few minutes)" if measure else ""))
    cmd = [sys.executable, str(HERE / "detect_gates.py"), str(repo), "--json"] + (["--run"] if measure else [])
    p = sh(cmd, timeout=3600)
    if p.returncode not in (0, 1) or not p.stdout.strip():
        die(f"could not detect gates: {p.stderr.strip()[:300]}")
    doc = json.loads(p.stdout)
    f.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def constraints_text(gates_doc, repo: Path) -> str:
    """What the kit requires, written in the plan's own vocabulary so it lands in Global Constraints."""
    gates = gates_doc.get("gates", [])
    lines = []
    for g in gates:
        b = g.get("baseline") or {}
        if g["kind"] == "live":
            lines.append(f"- Live gate `{g['command']}` (in `{g['dir']}`) is run by a human, never by a worker.")
        elif b.get("token"):
            lines.append(f"- `{g['command']}` (in `{g['dir']}`) must stay at or above its baseline: {b['token']}.")
        else:
            lines.append(f"- `{g['command']}` (in `{g['dir']}`) must pass.")
    return "\n".join([
        "- Every task's **Files:** list is the complete set of files that task may touch. A worker that "
        "needs a file outside it must stop and say so, not widen its own scope.",
        "- Never edit lockfiles, CI workflows, agent settings, or any test not named in the task.",
        "- No new dependencies. No network access during a task. No `git commit|push|stash|checkout|reset`.",
        "- Every claim needs evidence: `path:line` for a code fact, the exact command and its result for a gate.",
        *lines,
        "- A model verdict is a claim. The live gate and a human reading the diff are what close a task.",
    ])


def campaign_for(repo: Path, ask: str, explicit) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return (repo / ".kit" / slug(ask)).resolve()


DEFAULT_MODELS = {
    # No role ever inherits a harness default: a default is a decision nobody made (lessons/2026-09-11).
    "omp":      {"reader": "openrouter/z-ai/glm-5.3-flash", "orchestrator": "openrouter/z-ai/glm-5.3", "planner": "openrouter/z-ai/glm-5.3",
                 "implementer": "openrouter/z-ai/glm-5.3-flash", "verifier": "openrouter/z-ai/glm-5.3-flash"},
    "codex":    {"reader": "z-ai/glm-5.3-flash", "orchestrator": "z-ai/glm-5.3", "planner": "z-ai/glm-5.3",
                 "implementer": "z-ai/glm-5.3-flash", "verifier": "z-ai/glm-5.3-flash"},
    "claude":   {"reader": "claude-haiku-4-5-20251001", "orchestrator": "claude-sonnet-5", "planner": "claude-sonnet-5",
                 "implementer": "claude-sonnet-5", "verifier": "claude-haiku-4-5-20251001"},
}


def ensure_campaign(campaign: Path, repo: Path, harness: str, ask: str, gates_doc: dict) -> bool:
    """A campaign is a folder: config (models named per role, caps), the worker AGENTS file, the ask, the
    constraints the gates imply, and the folders the pipeline fills. Created silently on first use; the
    journal of what happened is crux's, not a ledger here."""
    if (campaign / "config.json").is_file():
        return False
    feature = slug(ask, 24)
    example = KIT / "templates" / "config.json"
    if not example.is_file():
        die(f"templates/config.json missing from {KIT}")
    cfg = json.loads(example.read_text())
    cfg.update({"harness": harness, "campaign": f"{repo.name}/{feature}", "campaign_baseline_usd": None,
                "models": dict(DEFAULT_MODELS.get(harness, DEFAULT_MODELS["omp"]))})
    (campaign / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (campaign / f"AGENTS-{feature}.md").write_text((KIT / "promptbooks" / "AGENTS.template.md").read_text().replace("<feature>", feature))
    for sub in ("packets", "receipts", "runs", "evidence", "fixtures"):
        (campaign / sub).mkdir(parents=True, exist_ok=True)
    (campaign / "ASK.md").write_text(f"# Ask\n\n{ask}\n")
    (campaign / "CONSTRAINTS.md").write_text(
        "# Global Constraints (injected into the plan by the kit)\n\n"
        + constraints_text(gates_doc, repo) + "\n")
    return True


def draft_packet(unit: str, behaviour: str, evidence, files, gates_doc: dict, campaign: Path, repo: Path) -> str:
    """The packet is drafted locally, from the template, in zero seconds for zero dollars. Yesterday's loop
    ($0.05–0.10, 15 min/unit) had the human and the orchestrator write packets by hand; today's attempt to
    have GLM-5.3 author one spent 4 minutes and $0.12 on an empty file. Models execute packets; they do
    not author them. The `<…>` spots are what the human fills in — usually three lines."""
    files = [f.strip() for f in (files or "").split(",") if f.strip()]
    tests = [f for f in files if re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(test|spec)\.", f)]
    src = [f for f in files if f not in tests]
    gates = [g for g in gates_doc.get("gates", []) if g.get("kind") != "live"]
    def gate_line(g):
        b = g.get("baseline") or {}
        tok = b.get("token") or ("exit 0" if b.get("exit") == 0 else "baseline red")
        return f"- `{g.get('command')}` — {g.get('gate')}: {tok} at baseline; must not regress, new §5 cases green"
    owned = "\n".join(f"- `{f}` — <what changes>" for f in src) or "- `<path>` — <what changes>"
    owned += "\n" + ("\n".join(f"- `{f}` — <cases added>" for f in tests) or "- `<test path>` — <cases added>")
    return f"""# Packet {unit} — {behaviour[:80]}

Status: DRAFT (human) → REVIEWED (human) → EXECUTED → VERIFIED
Campaign: {campaign.relative_to(repo)}. Evidence: {evidence or '<none — name the root cause below>'}.
Gap in one sentence: {behaviour}

## 1. Protected inputs (in addition to the AGENTS file)
- every file not listed in §2, and every existing test not named in §5

## 2. Owned files (EXCLUSIVE — the implementer edits nothing else)
{owned}

## 3. Todo DAG (each ≤ ~80 LOC, independently checkable)
1. write the failing test in {tests[0] if tests else '<test path>'} → run it → expect FAIL
2. <the minimum change> in {src[0] if src else '<path>'} → run the test → expect PASS
3. run the §6 gates

## 4. Structural evidence required before claiming
- `grep -n "<new symbol>" {src[0] if src else '<path>'}` — expected: present once

## 5. Real-boundary test
- {tests[0] if tests else '<test path>'}: <case name> asserts <observable behaviour> against the real artefact (no mocks)

## 6. Definition of done (fail-closed, with counts)
{chr(10).join(gate_line(g) for g in gates) or '- <gate> ≥ <baseline>'}

## 7. Checkpoint / resume predicate
- If time runs out: write `receipts/{unit}-execution.md` with the completed DAG steps and the failing
  command's output. Resume = re-run from the first unchecked step.

## 8. Out of scope (explicit)
- <tempting addition 1>
- <tempting addition 2>
- <tempting addition 3>
"""


def newest_campaign(repo: Path, campaign_arg):
    if campaign_arg:
        return Path(campaign_arg).resolve()
    cands = sorted((repo / ".kit").glob("*/config.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0].parent if cands else None


def packet_state(packet: Path, campaign: Path):
    status = next((l for l in packet.read_text().splitlines()[:6] if l.startswith("Status:")), "")
    unit = re.sub(r"[^A-Za-z0-9-]+", "-", packet.stem)[:24].strip("-")
    receipt = campaign / "receipts" / f"{unit}-receipt.md"
    if receipt.is_file() and receipt.read_text().startswith("VERDICT: ACCEPT"):
        return "accepted"
    if "REVIEWED" in status or "APPROVED" in status:
        return "approved"
    return "draft"


def unit_targets(cfg):
    """Per-unit flag thresholds: config.json unit_targets merged over the 0.15 USD / 15 min defaults."""
    t = {"usd": 0.15, "minutes": 15}
    t.update(cfg.get("unit_targets") or {})
    return t


def unit_totals(spend_rows):
    """Spend per unit from spend.jsonl rows: {unit: {"usd": total, "seconds": total}} (all rows, known or not)."""
    totals = {}
    for r in spend_rows:
        t = totals.setdefault(r.get("unit", "?"), {"usd": 0.0, "seconds": 0})
        t["usd"] += float(r.get("cost_usd") or 0.0)
        t["seconds"] += int(r.get("seconds") or 0)
    return totals


def gate_lines_from(record: Path):
    """The verifier's `gate:` lines, regenerated from the gate runner's record — same format, no drift."""
    try:
        rec = json.loads(record.read_text())
    except (OSError, ValueError):
        return []
    if not rec.get("results"):
        return []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gates", HERE / "gates.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return [mod.receipt_line(r) for r in rec["results"]]
    except Exception:
        return [f"{r.get('command', '?')} ({r.get('dir', '.')}) → exit {r.get('exit', '?')} — {r.get('token', '?')}"
                for r in rec["results"]]


def owned_paths(packet: Path):
    """The backticked paths of the packet's `## 2. Owned files` section — the only places a diff may touch."""
    owned, in_section = set(), False
    for line in packet.read_text().splitlines():
        if line.startswith("## "):
            in_section = line.startswith("## 2.")
            continue
        if in_section:
            owned.update(m for m in (t.strip() for t in re.findall(r"`([^`]+)`", line))
                         if m and " " not in m and not m.startswith(("<", "...")))
    return owned
