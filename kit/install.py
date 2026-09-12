#!/usr/bin/env python3
"""install.py — `kit install`: the first thing you run in any repository.

Three tiers, decided by what actually has to live where:

  1. Private overlay, never pushed        `<root>/.desoleary/` — rules, skills, command source,
                                          and every campaign artefact. Agents are pointed here by
                                          the repo's own AGENTS.md rule ("if a .desoleary/ directory
                                          exists, read and reference the skills, rules and guidance
                                          under it"), so nothing tracked has to change.
  2. Native harness paths, kept unpushed  `.claude/commands/`, `.cursor/commands/`, `.codex/prompts/`
                                          Slash commands are the one thing a harness will only find
                                          at a fixed path, so they are projected there and added to
                                          `.git/info/exclude` — a per-clone ignore that is never
                                          committed and never touches the repo's own .gitignore.
  3. Tracked files in the host repo       Never written. If the pointer rule is missing, the exact
                                          line is printed for a human to add.

No network, no fetch, nothing to fail closed on. `--with-rulesync` additionally runs
omnitech-rulesync for the full technology-profile treatment when it is installed.
"""
import os, shutil, subprocess, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SRC = KIT / "rulesync"
NATIVE = {"claude": ".claude/commands", "cursor": ".cursor/commands", "codex": ".codex/prompts"}
POINTER = ("If a `.desoleary/` directory exists, read and reference the skills, rules, and guidance "
           "under it. They apply only where they do not conflict with this file, repository "
           "instructions, or higher-priority instructions.")


def say(m=""):
    print(m, flush=True)


def _tracked(repo: Path, rel: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel],
                          capture_output=True).returncode == 0


def _ignored(repo: Path, rel: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", rel],
                          capture_output=True).returncode == 0


def exclude(repo: Path, patterns):
    """Per-clone ignore. Never the repo's .gitignore: this is our tooling in someone else's repo."""
    f = repo / ".git" / "info" / "exclude"
    if not f.parent.is_dir():
        return []
    have = f.read_text().splitlines() if f.is_file() else []
    add = [p for p in patterns if p not in have and not _ignored(repo, p)]
    if add:
        header = [] if any("omnitech-dev-kit" in l for l in have) else ["", "# omnitech-dev-kit (local only, never committed)"]
        f.write_text("\n".join(have + header + add).strip() + "\n")
    return add


def cmd_install(repo_arg=None, with_rulesync=False):
    from .campaign import repo_root, die
    repo = Path(repo_arg).resolve() if repo_arg else (repo_root() or die("not inside a git repository"))
    say(f"kit install: {repo}")

    # 1 — the private overlay
    overlay = repo / ".desoleary"
    dest = overlay / "rulesync"
    for sub in ("rules", "skills", "commands"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "rules" / "dev-kit.md", dest / "rules" / "dev-kit.md")
    skill_dst = dest / "skills" / "omnitech-dev-kit"
    skill_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "skills" / "omnitech-dev-kit" / "SKILL.md", skill_dst / "SKILL.md")
    shutil.copy2(SRC / "commands" / "kit-next.md", dest / "commands" / "kit-next.md")
    say(f"  overlay   .desoleary/rulesync/   rule + skill + command source")
    if _ignored(repo, ".desoleary"):
        say("  ignored   .desoleary already ignored here")
    else:
        added = exclude(repo, [".desoleary/"])
        say("  ignored   added .desoleary/ to .git/info/exclude (per-clone, never committed)")
        gi = subprocess.run(["git", "config", "--get", "core.excludesfile"],
                            capture_output=True, text=True).stdout.strip()
        if gi:
            say(f"            one-time fix for every repo: add `.desoleary` to {gi}")

    # 2 — slash commands, the one thing that must sit where each harness looks
    projected = []
    for name, rel in NATIVE.items():
        d = repo / rel
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / "commands" / "kit-next.md", d / "kit-next.md")
        projected.append(f"{rel}/kit-next.md")
    added = exclude(repo, projected)
    say(f"  commands  /kit-next projected to {', '.join(NATIVE.values())}")
    say(f"  ignored   {len(added)} native path(s) added to .git/info/exclude" if added
        else "  ignored   native paths already covered by your global gitignore")
    say("  source    vendored (no network). `--with-rulesync` adds the full technology profiles.")

    # 3 — tracked instruction files: report, never write
    say("")
    for name in ("AGENTS.md", "CLAUDE.md"):
        f = repo / name
        if not f.is_file():
            say(f"  {name:10s} absent — create it with the pointer line below if you want one")
            continue
        body = f.read_text()
        if ".desoleary" in body:
            say(f"  {name:10s} already points at .desoleary/ — nothing to do")
        elif _tracked(repo, name):
            say(f"  {name:10s} TRACKED and has no .desoleary pointer. Not edited. Add this line yourself:")
            say(f"      {POINTER}")
        else:
            say(f"  {name:10s} untracked and has no .desoleary pointer. Add this line:")
            say(f"      {POINTER}")

    # 4 — optional full rulesync pass
    if with_rulesync:
        cli = Path.home() / "dev" / "omnitech-solutions" / "omnitech-rulesync" / "dist" / "cli.js"
        if not cli.is_file():
            say("\n  rulesync  not found; the overlay above is complete on its own")
        else:
            say("\n  rulesync  running the full technology-profile install (needs network)…")
            r = subprocess.run(["node", str(cli), "install", str(repo), "--yes"],
                               capture_output=True, text=True)
            tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
            say(f"  rulesync  {'ok' if r.returncode == 0 else 'FAILED (non-fatal): ' + tail[0][:90]}")
            if r.returncode == 0:
                exclude(repo, [".rulesync/", ".claude/", ".cursor/", ".codex/", ".windsurf/", "rulesync.jsonc", "rulesync.lock"])

    say("\nNext:")
    say('  kit init <slug> --oracle "<reference system>" --subject "<ours>"')
    say('  kit ledger add "<one observable behaviour>"')
    say("  kit next")
    return 0
