#!/usr/bin/env python3
"""unit.py - worktree -> implementer -> gates -> one-turn verifier. One packet, one branch."""
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
from .campaign import gate_lines_from


def run_unit(repo: Path, campaign: Path, packet: Path, unit: str, name: str, last: bool, prev_unit):
    """worktree → implementer → gates → one-turn verifier → commit+tag on clean. Shared by the plan path
    (a projected Task) and the packet path (a hand-written unit)."""
    gates = campaign / "gates.json"
    n = unit
    tasks = [{"n": unit, "name": name}]
    wt = repo.parent / f"wt-{campaign.name}-{n}"
    branch = f"kit/{campaign.name}-{n.lower()}"            # branches/tags are lowercase: kit/<campaign>-t1
    if not wt.exists():
        prev = f"kit/{campaign.name}-{prev_unit.lower()}" if prev_unit else ""
        has_prev = bool(prev) and sh(["git", "-C", str(repo), "rev-parse", "--verify", "-q", prev]).returncode == 0
        base = prev if has_prev else sh(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        if has_prev:
            say(f"  chaining from {prev} (previous task's accepted branch)")
        r = sh(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(wt), base])
        if r.returncode != 0:
            die(f"could not create the worktree: {r.stderr.strip()[:300]}")
        say(f"  worktree {wt} on {branch} (from {base})")
        provision_worktree(repo, wt, campaign)
    else:
        say(f"  worktree {wt} (existing)")

    exec_receipt = campaign / "receipts" / f"{n}-execution.md"
    exec_receipt.parent.mkdir(parents=True, exist_ok=True)
    if "--verify-only" in sys.argv:
        # Re-run gates and the verifier over the worktree as it stands (the implementer already ran, or a
        # human edited the candidate). Nothing is re-implemented.
        say("\n  implementer skipped (--verify-only): verifying the worktree as it stands")
        rc = 0
    else:
      say("\n  implementer (guarded: exclusive scope, tool boundary, wall clock, budget)…")
      rc = subprocess.run([
        sys.executable, str(HERE / "run.py"), "implementer", f"{n}", str(wt),
        "--config", str(campaign / "config.json"), "--",
        f"@{campaign / f'AGENTS-{slug(campaign.name, 24)}.md'}" if (campaign / f"AGENTS-{slug(campaign.name,24)}.md").is_file()
        else f"@{packet}",
        f"@{KIT / 'promptbooks' / 'implement.md'}", f"@{packet}",
        f"Receipt path: {exec_receipt}. Run only the tests the packet names.",
      ], cwd=str(wt)).returncode
      say(f"  implementer exit {rc}")

    say("\n  gates (run by the kit, not by a model)…")
    gate_record = campaign / f"gates-run-{n}.json"
    scope = "full" if (last or "--full-gates" in sys.argv) else "selected"
    if scope == "selected":
        say("  gates: selected scope (fast, provisional) — the last task runs the full bar")
    gp = subprocess.run([sys.executable, str(HERE / "gates.py"), str(wt),
                         "--gates", str(gates), "--scope", scope, "--out", str(gate_record)],
                        cwd=str(wt))
    try:
        rec = json.loads(gate_record.read_text())
        say(f"  gates: {rec['ran']} run at {rec['scope']} scope, {rec['failed']} regression(s), "
            f"candidate {rec['candidate_digest']}, acceptance-eligible: {rec['acceptance_eligible']}")
    except (OSError, ValueError):
        say("  gates: no record produced — the verifier will be told the evidence is missing")

    # Materialise everything the verifier needs so it never has to go and look: one turn, no tools.
    diff_file = campaign / "receipts" / f"{n}.diff"
    diff_file.parent.mkdir(parents=True, exist_ok=True)
    base_ref = sh(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()
    tracked = sh(["git", "-C", str(wt), "diff", base_ref]).stdout
    untracked = sh(["git", "-C", str(wt), "ls-files", "--others", "--exclude-standard"]).stdout.split()
    parts = [f"# diff vs {base_ref[:12]}\n\n{tracked}"]
    for f in untracked:
        fp = wt / f
        if fp.is_file() and fp.stat().st_size < 200_000 and "node_modules" not in f:
            parts.append(f"\n\n# NEW FILE {f}\n\n{fp.read_text(errors='replace')}")
    diff_file.write_text("\n".join(parts))
    prefetch = [str(diff_file)] + ([str(gate_record)] if gate_record.is_file() else []) + \
               ([str(exec_receipt)] if exec_receipt.is_file() else [])
    say("\n  verifier (one turn, no tools: diff + gate record inlined; does not re-run gates)…")
    receipt = campaign / "receipts" / f"{n}-receipt.md"
    rc2 = subprocess.run([
        sys.executable, str(HERE / "run.py"), "verifier", f"{n}", str(wt),
        "--config", str(campaign / "config.json"), "--out", str(receipt), "--validate", "receipt",
        "--prefetch", ",".join(prefetch), "--",
        f"@{KIT / 'promptbooks' / 'verify.md'}", f"@{packet}",
        f"@{KIT / 'skills' / 'borrowed' / 'verify-test-teeth' / 'SKILL.md'}",
        f"You have NO tools and exactly one turn. The complete diff, every new file, the gate runner's record "
        f"and the implementer's receipt are inlined above — everything you need is already in front of you. "
        f"Do not ask to run or read anything. Copy the gate record's `gate:` lines verbatim. Judge the diff "
        f"against the packet and verify-test-teeth. Write the receipt as your entire answer, starting with "
        f"'VERDICT: ACCEPT' or 'VERDICT: REJECT'; it will be saved to {receipt}.",
    ], cwd=str(wt)).returncode
    say(f"  verifier exit {rc2}")

    ok = rc == 0 and rc2 == 0
    try:
        rec = json.loads(gate_record.read_text())
        # a selected run cannot be acceptance-eligible by design; "clean" for an intermediate task means
        # no regression, and the final full run decides acceptance for the chain
        ok = ok and (rec.get("acceptance_eligible", False) if scope == "full" else rec.get("failed", 1) == 0)
    except (OSError, ValueError):
        ok = False
    verdict = (receipt.read_text().strip().splitlines() or [""])[0] if receipt.is_file() else ""
    ok = ok and verdict == "VERDICT: ACCEPT"
    if ok:
        # Commit the accepted candidate on its own branch and tag it: the next task chains from here and
        # `git reset --hard <tag>` is the rollback. node_modules is gitignored, so the link/copy is not staged.
        sh(["git", "-C", str(wt), "add", "-A"])
        msg = f"kit({n}): {name[:60]}\n\nCampaign {campaign.name}. Gates {scope} scope; receipt {receipt.name}."
        c = subprocess.run(["git", "-C", str(wt), "-c", "user.name=kit", "-c", "user.email=kit@local", "commit", "-q", "-m", msg],
                           capture_output=True, text=True)
        sh(["git", "-C", str(wt), "tag", "-f", f"kit/{campaign.name}-{n.lower()}-after"])
        say(f"  committed on {branch} and tagged kit/{campaign.name}-{n.lower()}-after" if c.returncode == 0 else f"  commit skipped: {c.stderr.strip()[:80]}")
        head = sh(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"]).stdout.strip()
        crux_inbox_drop(repo, f"{campaign.name[:24]}-{n.lower()}", f"kit unit {n}: {name}",
            f"kind: journal\ncampaign: {campaign.name}\nunit: {n}\npacket: {packet.relative_to(repo)}\n"
            f"receipt: {receipt.relative_to(repo) if receipt.is_file() else '-'}\n"
            f"gates: {gate_record.relative_to(repo) if gate_record.is_file() else '-'} ({scope} scope)\n"
            f"branch: {branch} @ {head}   tag: kit/{campaign.name}-{n.lower()}-after\n"
            f"verdict: {verdict}\n\nWhat changed: {name}. Evidence: the receipt and gate record above; the diff is `git show {head}`.")
    else:
        say(f"  NOT clean (implementer {rc}, verifier {rc2}, verdict {verdict or 'none'}); nothing committed, next task will not chain from this")
    say("\n  what you own now:")
    say(f"    receipt   {receipt if receipt.is_file() else '(not written)'}")
    say(f"    diff      git -C {wt} diff HEAD~1" if ok else f"    diff      git -C {wt} diff")
    say(f"    live gate the plan's Global Constraints name it; a model never runs it")
    return 0 if ok else 1


def provision_worktree(repo: Path, wt: Path, campaign: Path):
    """A fresh worktree has the repo and nothing else. Give it the owner's environment deliberately:
    link what is heavy and safe (dependencies, the repo's agent config), copy what is small and per-tree
    (.env files), and NEVER expose live data (a local database) to a worker. All three lists come from
    config.json `worktree`; Claude Code's own `worktree.symlinkDirectories` in the repo's
    .claude/settings.json is honoured too, so one declaration serves both tools."""
    import fnmatch
    cfg = json.loads((campaign / "config.json").read_text()).get("worktree", {}) or {}
    link = list(cfg.get("link") or ["**/node_modules", ".claude"])
    copy = list(cfg.get("copy") or [".env", ".env.local", "*/.env", "*/.env.local"])
    never = list(cfg.get("never") or ["**/.local-runtime", ".local-runtime", "**/*.sqlite", "**/*.db"])
    for sf in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        try:
            link += json.loads(sf.read_text()).get("worktree", {}).get("symlinkDirectories", [])
        except (OSError, ValueError):
            pass
    ignored = sh(["git", "-C", str(repo), "status", "--ignored", "--porcelain"]).stdout
    candidates = [l[3:].rstrip("/") for l in ignored.splitlines() if l.startswith("!!")]
    linked, copied, refused = [], [], []
    def matches(path, pats):
        return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path.split("/")[-1], p.split("/")[-1]) and "**" in p
                   for p in pats)
    for rel in candidates:
        src = repo / rel
        dst = wt / rel
        if dst.exists() or not src.exists():
            continue
        if matches(rel, never):
            refused.append(rel); continue
        if matches(rel, link) and src.is_dir():
            dst.parent.mkdir(parents=True, exist_ok=True); dst.symlink_to(src); linked.append(rel)
        elif matches(rel, copy) and src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(src.read_bytes()); copied.append(rel)
    if linked: say(f"  env: linked {', '.join(linked)}")
    if copied: say(f"  env: copied {', '.join(copied)}")
    if refused: say(f"  env: NOT exposed to the worker (live data): {', '.join(refused)}")
