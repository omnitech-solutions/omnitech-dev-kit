#!/usr/bin/env python3
"""probe.py — read the repository, decide nothing.

Two jobs, both read-only:

  environment()  where the app lives and how to run it. A worker cannot know that this app is under
                 `adapter/`; today the packet carries it by hand or the worker guesses.

  house_rules()  the AI instructions this repository already has. These OUTRANK ours. We are the
                 guest: a repo with an AGENTS.md has already decided things, and the kit's job is to
                 find them and obey, never to rewrite them.

Nothing here writes to the repository. `kit install` records what this returns into our own config
under `.desoleary/`, and the repo's files are never touched.
"""
import json, re
from pathlib import Path

# Highest precedence first. The kit's own overlay is deliberately last.
HOUSE_FILES = [
    ("AGENTS.md", "repo instructions"),
    ("CLAUDE.md", "repo instructions"),
    ("GEMINI.md", "repo instructions"),
    ("CONVENTIONS.md", "aider conventions"),
    (".github/copilot-instructions.md", "copilot instructions"),
]
HOUSE_DIRS = [
    (".cursor/rules", "cursor rules"),
    (".claude", "claude project config"),
    (".codex", "codex config"),
    (".windsurf", "windsurf rules"),
    (".rulesync/rules", "rulesync source"),
]
SCRIPT_ROLES = {
    "dev": ("dev", "start", "serve"),
    "test": ("test:product", "test", "test:unit"),
    "typecheck": ("typecheck", "tsc", "types"),
    "build": ("build",),
    "lint": ("lint", "ast:scan"),
}
LOCKS = {"package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lockb": "bun"}


def _pkg(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def app_root(repo: Path):
    """The nearest package.json that actually has a dev script, preferring the shallowest.

    A monorepo root whose `dev` merely delegates ("cd adapter && npm run dev") is not the app root;
    the directory it delegates to is. That single fact is what a worker cannot guess.
    """
    candidates = []
    for p in sorted(repo.glob("*/package.json")) + ([repo / "package.json"] if (repo / "package.json").is_file() else []):
        doc = _pkg(p)
        scripts = doc.get("scripts") or {}
        if scripts:
            candidates.append((p.parent, scripts))
    if not candidates:
        return repo, {}
    root_scripts = dict(candidates[-1][1]) if candidates[-1][0] == repo else {}
    dev = root_scripts.get("dev", "")
    m = re.search(r"cd\s+([\w./-]+)", dev)
    if m:
        target = (repo / m.group(1)).resolve()
        for d, s in candidates:
            if d.resolve() == target:
                return d, s
    for d, s in candidates:
        if any(k in s for k in ("dev", "start")) and d != repo:
            return d, s
    return candidates[-1]


def dev_url(repo: Path, root: Path):
    launch = repo / ".claude" / "launch.json"
    if launch.is_file():
        doc = _pkg(launch)
        for c in doc.get("configurations", []):
            if c.get("url"):
                return c["url"]
            if c.get("port"):
                return f"http://127.0.0.1:{c['port']}"
    for name in ("vite.config.ts", "vite.config.js", "next.config.js"):
        f = root / name
        if f.is_file():
            m = re.search(r"port\s*[:=]\s*(\d{4,5})", f.read_text())
            if m:
                return f"http://127.0.0.1:{m.group(1)}"
    return None


def environment(repo: Path) -> dict:
    root, scripts = app_root(repo)
    pm = next((v for k, v in LOCKS.items() if (root / k).is_file() or (repo / k).is_file()), None)
    commands, notes = {}, []
    if scripts:
        runner = f"{pm or 'npm'} run"
        for role, names in SCRIPT_ROLES.items():
            hit = next((n for n in names if n in scripts), None)
            if hit:
                commands[role] = f"{runner} {hit}"
    if (repo / "pyproject.toml").is_file():
        commands.setdefault("test", "pytest -q")
    if (repo / "mix.exs").is_file():
        commands.setdefault("test", "mix test")
    if pm in ("pnpm", "npm") and not (root / f"{'pnpm-lock.yaml' if pm == 'pnpm' else 'package-lock.json'}").is_file():
        notes.append(f"no lockfile committed under {root.name}/ — worktrees should symlink "
                     f"{root.name}/node_modules from the host checkout rather than install")
    return {
        "app_root": str(root.relative_to(repo)) if root != repo else ".",
        "package_manager": pm,
        "install": {"npm": "npm ci", "pnpm": "pnpm install --offline", "yarn": "yarn install"}.get(pm),
        "commands": commands,
        "dev_url": dev_url(repo, root),
        "monorepo": root != repo,
        "notes": notes,
    }


def house_rules(repo: Path, max_lines=200) -> dict:
    """Index the repo's existing AI instructions. Read-only, and precedence-ordered."""
    found, budget = [], max_lines
    for rel, what in HOUSE_FILES:
        f = repo / rel
        if not f.is_file():
            continue
        lines = len(f.read_text().splitlines())
        found.append({"path": rel, "kind": what, "lines": lines,
                      "inject": lines <= budget, "reason": None if lines <= budget else
                      f"{lines} lines exceeds the remaining {budget}-line budget; referenced by path only"})
        if lines <= budget:
            budget -= lines
    for rel, what in HOUSE_DIRS:
        d = repo / rel
        if d.is_dir() and any(d.iterdir()):
            found.append({"path": rel, "kind": what, "lines": None, "inject": False,
                          "reason": "directory — referenced by path, never inlined"})
    try:
        from .crux import docs_dir
        if (dd := docs_dir(repo)):
            found.append({"path": str(dd.relative_to(repo)), "kind": "crux tree", "lines": None,
                          "inject": False, "reason": "large generated tree — referenced by path"})
    except Exception:
        pass
    return {"precedence": "house rules outrank the kit's own rules; the kit is the guest here",
            "max_lines": max_lines, "found": found}
