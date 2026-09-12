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


def run_stage(argv, cwd, label, cap_s=None, campaign=None):
    """Launch a stage and print a heartbeat while it runs.

    A stage that prints nothing for four minutes is indistinguishable from a hung one. The child's
    own output still streams straight through; this only adds an elapsed line so the caller (and a
    background task chip) always shows movement.
    """
    import threading
    from .settings import load as load_settings, output_for
    s, _ = load_settings(campaign)
    o = output_for(s, label)
    every = int(o.get("heartbeat_seconds") or 0)
    logf = o.get("log")
    start = time.time()
    stop = threading.Event()

    def emit(line):
        if o.get("console", True):
            say(line)
        if logf:
            with open(logf, "a") as f:
                f.write(line + "\n")

    def tick():
        while not stop.wait(every):
            el = int(time.time() - start)
            emit(f"    … {label} {el // 60}m{el % 60:02d}s" + (f" of {cap_s // 60}m cap" if cap_s else ""))

    if every > 0:
        threading.Thread(target=tick, daemon=True).start()
    try:
        rc = subprocess.run(argv, cwd=cwd).returncode
    finally:
        stop.set()
    el = int(time.time() - start)
    emit(f"  {label} exit {rc} after {el // 60}m{el % 60:02d}s")
    return rc


def house_parts(repo: Path):
    """The repo's own AI instructions, first in the prompt, ahead of anything of ours.

    Constraints frame the task, so they come before it. Until 2026-09-12 no worker had ever seen
    this repo's AGENTS.md — including its "No mock tests. Zero." — which held only because the
    orchestrator typed it into each packet by hand.
    """
    cfg = repo / ".desoleary" / "kit" / "kit.json"
    if not cfg.is_file():
        return [], []
    try:
        doc = json.loads(cfg.read_text())
    except ValueError:
        return [], []
    parts = [f"@{repo / h['path']}" for h in (doc.get("house_rules") or {}).get("found", [])
             if h.get("inject") and (repo / h["path"]).is_file()]
    env = doc.get("environment") or {}
    lines = [f"Repository facts (detected by kit install; do not guess these):",
             f"  app root: {env.get('app_root')}   package manager: {env.get('package_manager')}"]
    for role, cmd in (env.get("commands") or {}).items():
        lines.append(f"  {role}: `{cmd}`  (run from {env.get('app_root')})")
    if env.get("dev_url"):
        lines.append(f"  the running app: {env['dev_url']}")
    for n in env.get("notes") or []:
        lines.append(f"  note: {n}")
    refs = [h["path"] for h in (doc.get("house_rules") or {}).get("found", []) if not h.get("inject")]
    if refs:
        lines.append(f"  this repository's other standing instructions live at: {', '.join(refs)}")
    lines.append("These repository rules outrank anything in the kit's promptbooks or this packet. "
                 "If the packet asks for something they forbid, stop and say so.")
    return parts, ["\n".join(lines)]


TROUBLE = ("diverged", "could not write", "failed to write", "editor state", "tool error",
           "unable to edit", "write failed")


def host_status(repo: Path) -> str:
    """A fingerprint of the checkout you launched from — whatever branch that is, not `main`.

    A worker must never touch it (FF-09, 2026-09-10: absolute paths leaked from a receipt and the
    implementer edited the host checkout as well as its own worktree).
    """
    return sh(["git", "-C", str(repo), "status", "--porcelain"]).stdout


def incomplete_receipt(campaign: Path, repo: Path, wt: Path, unit: str, role: str, rc: int, log_tail=""):
    """The kit writes this, because a model killed by the wall clock cannot.

    Packet §7 asks the worker to record what it finished. That works when a gate fails, and not at
    all when the process is killed — which is exactly the case where you would otherwise have
    nothing to show for 90% of an implementation.
    """
    stat = sh(["git", "-C", str(wt), "diff", "--stat"]).stdout.strip()
    files = [l[3:].strip() for l in sh(["git", "-C", str(wt), "status", "--porcelain"]).stdout.splitlines()]
    why = {124: "wall clock", 3: "per-run cost cap", 4: "budget", 125: "loop watchdog"}.get(rc, f"exit {rc}")
    f = campaign / "receipts" / f"{unit}-execution.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"""STATUS: INCOMPLETE ({role} stopped by {why})

Written by the kit, not by the model: a stopped worker cannot report on itself.

worktree: {wt}
branch:   {sh(["git", "-C", str(wt), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()}
changed:  {len(files)} file(s)
{stat or '  (no changes on disk)'}

files:
{chr(10).join('  ' + x for x in files) or '  none'}

The work above is on disk and is NOT lost. Choose one:
  resume   kit next                      # re-runs the packet against this worktree, keeping the work
  discard  git -C {wt} checkout -- .
  inspect  git -C {wt} diff

last output before the stop:
{log_tail.strip()[-1200:] or '  (nothing captured)'}
""")
    return f


def receipt_trouble(campaign: Path, unit: str):
    """A receipt that mentions tool trouble is RED until re-run (FF-09: an implementer reported
    typecheck clean and seven tests green while the file on disk did not compile)."""
    f = campaign / "receipts" / f"{unit}-execution.md"
    if not f.is_file():
        return []
    low = f.read_text().lower()
    return [w for w in TROUBLE if w in low]


def preflight(repo: Path, campaign: Path, packet: Path, wt: Path, n: str):
    """Check EVERY stage's inputs before spending a cent on the first one.

    Bought on 2026-09-12: an implementer ran 433s and $0.02, then the verifier died instantly
    because `skills/borrowed/verify-test-teeth/SKILL.md` was missing — knowable in zero seconds.
    A unit must fail in the first second or not at all.
    """
    agents = campaign / f"AGENTS-{slug(campaign.name, 24)}.md"
    parts = {
        "packet": packet,
        "config": campaign / "config.json",
        "implement promptbook": KIT / "promptbooks" / "implement.md",
        "verify promptbook": KIT / "promptbooks" / "verify.md",
        "preamble": KIT / "promptbooks" / "WHO-YOU-ARE.md",
        "verify-test-teeth skill": KIT / "skills" / "borrowed" / "verify-test-teeth" / "SKILL.md",
        "gate runner": HERE / "gates.py",
        "runner": HERE / "run.py",
        "gates.json": campaign / "gates.json",
    }
    if agents.is_file():
        parts["campaign AGENTS"] = agents
    missing = [f"{k}: {v}" for k, v in parts.items() if not Path(v).is_file()]

    # every role this unit will use must name a model, and the adapter must exist
    try:
        cfg = json.loads((campaign / "config.json").read_text())
    except (OSError, ValueError) as e:
        missing.append(f"config unreadable: {e}")
        cfg = {}
    for role in ("implementer", "verifier"):
        if not (cfg.get("models") or {}).get(role) and not (cfg.get("roles") or {}).get(role, {}).get("model"):
            missing.append(f"no model named for role {role!r} (a default nobody chose is a bug)")
    adapter = KIT / "harness" / f"{cfg.get('harness', 'omp')}.sh"
    if not adapter.is_file():
        missing.append(f"harness adapter: {adapter}")

    if missing:
        say("\n  PREFLIGHT FAILED — nothing was spent:")
        for m in missing:
            say(f"    missing  {m}")
        die("fix the above and run `kit next` again. Every stage's inputs are checked before the "
            "first one runs, so this costs you seconds rather than a whole unit.", 5)
    say(f"  preflight ok ({len(parts)} inputs, both stages)")
    return host_status(repo)


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
        # The base is a decision about THIS unit, never the repo's default branch: --base wins,
        # then the previous accepted unit when chaining, then the branch you invoked from.
        explicit = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else None
        cfg_base = (json.loads((campaign / "config.json").read_text()).get("worktree") or {}).get("base") \
            if (campaign / "config.json").is_file() else None
        base = explicit or (prev if has_prev else None) or cfg_base or \
            sh(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        if explicit:
            say(f"  base {base} (--base)")
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
      host_before = preflight(repo, campaign, packet, wt, n)
      say("\n  implementer (guarded: exclusive scope, tool boundary, wall clock, budget)…")
      house, facts = house_parts(repo)
      rc = run_stage([
        sys.executable, str(HERE / "run.py"), "implementer", f"{n}", str(wt),
        "--config", str(campaign / "config.json"), "--",
        *house, *facts,
        f"@{campaign / f'AGENTS-{slug(campaign.name, 24)}.md'}" if (campaign / f"AGENTS-{slug(campaign.name,24)}.md").is_file()
        else f"@{packet}",
        f"@{KIT / 'promptbooks' / 'implement.md'}", f"@{packet}",
        f"Receipt path: {exec_receipt}. Run only the tests the packet names.",
      ], cwd=str(wt), label="implementer", cap_s=720, campaign=campaign)

      if host_status(repo) != host_before:
          say("\n  THE CHECKOUT YOU LAUNCHED FROM CHANGED during the run. A worker must only touch its worktree.")
          say("    Inspect `git -C %s status` before trusting anything here." % repo)
          from .watchdog import halt_file
          halt_file(campaign).write_text(json.dumps({
              "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "unit": n, "role": "implementer",
              "reasons": ["the checkout the unit was launched from changed while a worker ran (FF-09)"],
              "clear_with": "kit resume, after you have checked and reverted main",
          }, indent=2) + "\n")
          die("halted: the checkout you launched from changed during a worker run", 4)

      if rc != 0 and not exec_receipt.is_file():
          log = next(iter(sorted((campaign / "runs").glob(f"*implementer-{n}.log"), reverse=True)), None)
          f = incomplete_receipt(campaign, repo, wt, n, "implementer", rc,
                                 log.read_text() if log and log.is_file() else "")
          say(f"  wrote {f.relative_to(repo)} — the partial work is kept in the worktree, not lost")

      if (words := receipt_trouble(campaign, n)):
          say(f"  receipt mentions tool trouble ({', '.join(words)}) — treating it as RED; "
              f"the verifier re-runs every gate itself")

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
    rc2 = run_stage([
        sys.executable, str(HERE / "run.py"), "verifier", f"{n}", str(wt),
        "--config", str(campaign / "config.json"), "--out", str(receipt), "--validate", "receipt",
        "--prefetch", ",".join(prefetch), "--",
        f"@{KIT / 'promptbooks' / 'verify.md'}", f"@{packet}",
        *[f"@{f}" for f in [KIT / "skills" / "borrowed" / "verify-test-teeth" / "SKILL.md"] if f.is_file()],
        f"You have NO tools and exactly one turn. The complete diff, every new file, the gate runner's record "
        f"and the implementer's receipt are inlined above — everything you need is already in front of you. "
        f"Do not ask to run or read anything. Copy the gate record's `gate:` lines verbatim. Judge the diff "
        f"against the packet and verify-test-teeth. Write the receipt as your entire answer, starting with "
        f"'VERDICT: ACCEPT' or 'VERDICT: REJECT'; it will be saved to {receipt}.",
    ], cwd=str(wt), label="verifier", cap_s=540, campaign=campaign)


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
