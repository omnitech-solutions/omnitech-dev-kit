#!/usr/bin/env python3
"""install.py — `kit install`: the one setup command, run once, in any repository.

Scope, deliberately narrow: it writes **only** into `.desoleary/` (ours) and the harness command
directories your global gitignore already covers. It never edits a tracked file, and it never
rewrites the repository's own AI instructions — it *reads* them, records where they are, and
declares the kit subordinate to them. A repo with an AGENTS.md has already decided things.

Because it owns nothing of the repo's, re-running is harmless by construction — which is why there
is no `update` and no `reset` and no ownership manifest. Decisions you make here are kept; detected
facts (dev port, gates, house rules) refresh on a re-run, so the same command stays correct as the
repo changes.

Interaction: **automatic by default**. It probes, takes every detected value, writes, and prints
what it did — so an orchestrator (me, codex, opencode, CI) can run it unattended and it can never
block. `--interactive` opts into four questions, each pre-filled from what was detected: Enter
accepts, `s` skips the rest, `?` explains, `q` cancels before anything is written.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SRC = KIT / "rulesync"
NATIVE = {"claude": ".claude/commands", "cursor": ".cursor/commands", "codex": ".codex/prompts"}
POINTER = ("If a `.desoleary/` directory exists, read and reference the skills, rules, and guidance "
           "under it. They apply only where they do not conflict with this file, repository "
           "instructions, or higher-priority instructions.")


def say(m=""):
    print(m, flush=True)


def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _ignored(repo: Path, rel: str) -> bool:
    return _git(repo, "check-ignore", "-q", rel).returncode == 0


def exclude(repo: Path, patterns):
    """Per-clone ignore only. Never the repo's .gitignore: this is our tooling in someone else's repo."""
    f = repo / ".git" / "info" / "exclude"
    if not f.parent.is_dir():
        return []
    have = f.read_text().splitlines() if f.is_file() else []
    add = [p for p in patterns if p not in have and not _ignored(repo, p)]
    if add:
        head = [] if any("omnitech-dev-kit" in l for l in have) else ["", "# omnitech-dev-kit (local only)"]
        f.write_text("\n".join(have + head + add).strip() + "\n")
    return add


class Asker:
    """Enter accepts, `s` skips the rest, `?` explains. No TTY means defaults, never a hang."""

    def __init__(self, interactive: bool):
        # Automatic is the default: an orchestrator running unattended must never meet a prompt.
        self.on = interactive and sys.stdin.isatty()
        self.skipped = not self.on
        self.answers = {}

    def offer_skip(self, n: int) -> bool:
        if not self.on:
            say("\n  automatic: taking every detected value (`kit install --interactive` to be asked)")
            return True
        say(f"\n  {n} questions, all pre-filled from what was detected.")
        try:
            r = input("  Enter = answer them · s = skip and accept all defaults · q = quit: ").strip().lower()
        except EOFError:
            return True
        if r == "q":
            raise SystemExit("kit install: cancelled, nothing written")
        self.skipped = r == "s"
        return self.skipped

    def ask(self, i, n, label, default, explain=""):
        if self.skipped:
            self.answers[label] = default
            return default
        shown = default if default not in (None, "") else "none"
        while True:
            try:
                r = input(f"  {i}/{n}  {label} [{shown}]: ").strip()
            except EOFError:
                r = ""
            if r == "?":
                say(f"        {explain or 'no further detail'}")
                continue
            if r.lower() == "s":
                self.skipped = True
                r = ""
            self.answers[label] = r or default
            return self.answers[label]


def cmd_install(repo_arg=None, interactive=False):
    from .campaign import repo_root, die
    from .probe import environment, house_rules
    repo = Path(repo_arg).resolve() if repo_arg else (repo_root() or die("not inside a git repository"))
    cfg_path = repo / ".desoleary" / "kit" / "kit.json"
    prior = {}
    if cfg_path.is_file():
        try:
            prior = json.loads(cfg_path.read_text())
        except ValueError:
            prior = {}
        say(f"kit install: already installed — refreshing detected facts, keeping your answers")
    else:
        say(f"kit install: {repo}")

    # ---- probe (read-only) ------------------------------------------------------------------
    env = environment(repo)
    house = house_rules(repo)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "HEAD"
    harnesses = [h for h in ("omp", "claude", "codex", "opencode") if shutil.which(h)]

    say("\n  detected")
    say(f"    app root        {env['app_root']}" + ("   (monorepo)" if env["monorepo"] else ""))
    say(f"    package manager {env['package_manager'] or 'none'}")
    for role, cmd in (env["commands"] or {}).items():
        say(f"    {role:15s} {cmd}")
    say(f"    dev url         {env['dev_url'] or 'not detected'}")
    say(f"    branch          {branch}")
    say(f"    harnesses       {', '.join(harnesses) or 'none found'}")
    for n in env["notes"]:
        say(f"    note            {n}")

    say("\n  house rules found (these OUTRANK the kit's own rules — the kit is the guest)")
    if not house["found"]:
        say("    none — the kit's rules apply unopposed")
    for h in house["found"]:
        how = "injected into every worker prompt" if h["inject"] else (h["reason"] or "referenced by path")
        say(f"    {h['path']:34s} {h['kind']:22s} {how}")

    # ---- ask only what probing could not settle ----------------------------------------------
    a = Asker(interactive)
    a.offer_skip(4)
    app_root = a.ask(1, 4, "app root", env["app_root"],
                     "where the app actually runs; workers are told this so they never guess")
    url = a.ask(2, 4, "dev url", env["dev_url"] or "",
                "the running app the orchestrator checks behaviour against at the live gate")
    run_cap = a.ask(3, 4, "per-run cost cap (USD)", prior.get("caps", {}).get("run_usd", 0.25),
                    "one model call. A run projected above this refuses before launching.")
    session_cap = a.ask(4, 4, "session cost cap (USD)", prior.get("caps", {}).get("session_usd", 2.00),
                        "all runs in a session, across every campaign and repo on this machine")

    # ---- write, only into our own territory ---------------------------------------------------
    env["app_root"], env["dev_url"] = app_root, (url or None)
    doc = {
        "_": "Written by kit install. Only the kit reads this; the repo's own rules always win.",
        "repo": {"default_branch": branch,
                 "_branch_note": "recorded for reference. A unit's worktree is based on the branch "
                                 "you invoke from, or --base, never on this."},
        "environment": env,
        "house_rules": house,
        "caps": {**(prior.get("caps") or {}),
                 "run_usd": float(run_cap), "session_usd": float(session_cap)},
        "harnesses": harnesses,
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(doc, indent=2) + "\n")

    dest = repo / ".desoleary" / "rulesync"
    for sub in ("rules", "skills/omnitech-dev-kit", "commands"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "rules" / "dev-kit.md", dest / "rules" / "dev-kit.md")
    shutil.copy2(SRC / "skills" / "omnitech-dev-kit" / "SKILL.md", dest / "skills" / "omnitech-dev-kit" / "SKILL.md")
    projected = []
    for name in sorted((SRC / "commands").glob("*.md")):
        shutil.copy2(name, dest / "commands" / name.name)
        for rel in NATIVE.values():
            (repo / rel).mkdir(parents=True, exist_ok=True)
            shutil.copy2(name, repo / rel / name.name)
            projected.append(f"{rel}/{name.name}")
    exclude(repo, [".desoleary/"] + projected)

    say(f"\n  wrote  {cfg_path.relative_to(repo)}")
    say(f"  wrote  .desoleary/rulesync/  (rules, skill, command source)")
    say(f"  wrote  {len(projected)} command file(s) into {', '.join(NATIVE.values())}")
    if not _ignored(repo, ".desoleary"):
        gi = subprocess.run(["git", "config", "--get", "core.excludesfile"],
                            capture_output=True, text=True).stdout.strip()
        say(f"  ignored via .git/info/exclude" + (f" — for every repo, add `.desoleary` to {gi}" if gi else ""))

    for name in ("AGENTS.md", "CLAUDE.md"):
        f = repo / name
        if f.is_file() and ".desoleary" not in f.read_text():
            say(f"\n  {name} has no pointer to .desoleary/. It is tracked, so the kit will not edit it.")
            say(f"  Add this line yourself if you want agents to read our overlay:\n      {POINTER}")

    _examples(repo, env, house)
    return 0


def _examples(repo: Path, env: dict, house: dict):
    say("""
  ─────────────────────────────────────────────────────────────────────────────
  Your first unit

    kit init parity --oracle "<the reference system + how to observe it>" \\
                    --subject "{url}"
    kit ledger add "<one thing you can observe in both systems>"
    kit next            # tells you which fixtures to capture — you drive the browsers
    kit next            # drafts the packet (0s, $0); you fill the <…> blanks
    kit next            # runs it: worktree, worker, gates, verifier
    kit next            # prints your verification steps; you check it live
    kit next            # commits and tags

  `kit next` is the only verb you need. It is idempotent: run it twice, get the same
  answer twice. It stops at every point a human should decide, and never spends while
  a packet still has blanks.

  Other commands
    kit status          ledger, cost per unit vs target, anything halted
    kit home            spend this session and today, across every repo
    kit resume          clear a watchdog halt after you have read why
    kit config explain caps.run_usd     why a setting has the value it has

  References
    .desoleary/kit/kit.json             what was detected here, and your answers
    .desoleary/rulesync/rules/          what any agent in this repo is told
    {kit}/promptbooks/ORCHESTRATOR.md   the six things to check before accepting a unit
    {kit}/templates/PACKET.md           the eight sections of a packet
""".format(url=env.get("dev_url") or "http://127.0.0.1:PORT", kit=KIT))
    if house["found"]:
        say(f"  This repo's own rules ({', '.join(h['path'] for h in house['found'][:3])}) come first;"
            f"\n  workers read them before anything of ours.\n")
