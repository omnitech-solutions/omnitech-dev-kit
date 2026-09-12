#!/usr/bin/env python3
"""detect_gates.py — propose a repo's gates instead of making a human type them (stdlib only).

usage: detect_gates.py [repo] [--run] [--json]

The gates table is the most valuable and most tedious artefact in a campaign: it is the definition of
done, and it is only useful with REAL baseline counts. A repo already declares its gates — package.json
scripts, a Makefile, pyproject tool config. This reads those and proposes a table.

--run executes each proposed gate once and records its exit code and a count token, so the baseline is
measured rather than guessed. Without it the table is a proposal with no baselines, and says so.

Proposals are ordered cheap-to-expensive, because that is the order a verifier should run them in.
Nothing is written: the caller decides what to keep.
"""
import json, shutil, re, subprocess, sys
from pathlib import Path

# name → (regexes matching a script/target name, kind, rough cost rank)
WANTED = [
    ("types",      [r"^(typecheck|tsc|types?|type-check)$"],                  "types",      1),
    ("lint",       [r"^(lint|eslint|ruff|flake8|rubocop)$"],                  "lint",       1),
    ("structural", [r"^(ast:scan|ast-scan|structural|semgrep)$"],             "structural", 2),
    ("unit",       [r"^(test|tests|test:unit|test:product|unit|pytest)$"],    "unit",       3),
    ("rail",       [r"^(test:rail|rail|contract|test:contract)$"],            "unit",       3),
    ("build",      [r"^(build|compile)$"],                                    "build",      4),
    ("e2e",        [r"^(e2e|test:e2e|e2e:.*|browser|integration)$"],          "live",       5),
]
COUNT_RE = re.compile(r"(\d+)\s+(passed|passing|tests?|findings?|errors?|problems?)", re.I)


def npm_scripts(pkg: Path):
    try:
        doc = json.loads(pkg.read_text())
    except (ValueError, OSError):
        return {}
    return doc.get("scripts", {}) or {}


def runner_for(repo: Path) -> tuple[str, str]:
    """(runner, evidence). A repo that commits no lockfile still usually reveals its runner in CI;
    when nothing does, say so rather than defaulting silently — the wrong runner is a gate that
    never runs."""
    for name, runner in (("pnpm-lock.yaml", "pnpm"), ("pnpm-workspace.yaml", "pnpm"),
                         ("yarn.lock", "yarn"), ("package-lock.json", "npm run"),
                         ("bun.lockb", "bun run")):
        for where in (repo, *[d for d in repo.iterdir() if d.is_dir() and not d.name.startswith(".")][:8]):
            if (where / name).is_file():
                return runner, f"{(where / name).relative_to(repo)}"
    for pkg in (repo / "package.json", *(repo.glob("*/package.json"))):
        if pkg.is_file():
            try:
                pm = json.loads(pkg.read_text()).get("packageManager")
            except (ValueError, OSError):
                pm = None
            if pm:
                return pm.split("@")[0] + (" run" if pm.startswith("npm") else ""), f"{pkg.relative_to(repo)} packageManager"
    ci = list((repo / ".github" / "workflows").glob("*.yml")) + list((repo / ".github" / "workflows").glob("*.yaml"))
    for f in ci[:12]:
        try:
            text = f.read_text()
        except OSError:
            continue
        for token, runner in (("pnpm ", "pnpm"), ("yarn ", "yarn"), ("npm run ", "npm run")):
            if token in text:
                return runner, f"{f.relative_to(repo)}"
    return "npm run", "NO EVIDENCE — assumed; confirm before trusting these commands"


def make_targets(mk: Path):
    try:
        text = mk.read_text()
    except OSError:
        return []
    return [m.group(1) for m in re.finditer(r"^([a-zA-Z][\w:-]*):(?!=)", text, re.M)]


def propose(repo: Path):
    out = []
    seen = set()
    # Node workspaces: the root, then any directory with its own package.json one level down.
    pkgs = [repo / "package.json"] + [p / "package.json" for p in sorted(repo.iterdir())
                                      if p.is_dir() and (p / "package.json").is_file()][:6]
    for pkg in pkgs:
        if not pkg.is_file():
            continue
        where = pkg.parent
        rel = "." if where == repo else str(where.relative_to(repo))
        runner, runner_evidence = runner_for(repo)
        for name, script in npm_scripts(pkg).items():
            for gate, pats, kind, rank in WANTED:
                if any(re.match(p, name) for p in pats):
                    key = (rel, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"gate": gate, "kind": kind, "rank": rank, "dir": rel,
                                "command": f"{runner} {name}", "source": str(pkg.relative_to(repo)),
                                "script": script[:80], "runner_evidence": runner_evidence})
    mk = repo / "Makefile"
    if mk.is_file():
        for target in make_targets(mk):
            for gate, pats, kind, rank in WANTED:
                if any(re.match(p, target) for p in pats) and (".", target) not in seen:
                    seen.add((".", target))
                    out.append({"gate": gate, "kind": kind, "rank": rank, "dir": ".",
                                "command": f"make {target}", "source": "Makefile", "script": ""})
    if (repo / "pyproject.toml").is_file():
        # Only tools the project actually configures become gates: a gate whose tool is not installed
        # measures red at baseline and then hides every real regression behind "no_regression".
        py = (repo / "pyproject.toml").read_text()
        uv = shutil.which("uv") is not None
        cands = [("unit", ("uv run --with pytest " if uv else "") + "python3 -m pytest -q", "unit", 3)]
        if "[tool.mypy]" in py: cands.append(("types", ("uv run --with mypy " if uv else "") + "mypy .", "types", 1))
        if "[tool.ruff]" in py: cands.append(("lint", ("uv run --with ruff " if uv else "") + "ruff check .", "lint", 1))
        for gate, cmd, kind, rank in cands:
            out.append({"gate": gate, "kind": kind, "rank": rank, "dir": ".", "command": cmd,
                        "source": "pyproject.toml", "script": ""})
    out.sort(key=lambda g: (g["rank"], g["dir"], g["gate"]))
    return out


def measure(repo: Path, gate: dict, timeout=900):
    cwd = repo / gate["dir"]
    try:
        p = subprocess.run(gate["command"], shell=True, cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit": 124, "token": f"timed out after {timeout}s"}
    blob = (p.stdout or "") + (p.stderr or "")
    m = None
    for m in COUNT_RE.finditer(blob):
        pass  # last match is usually the summary line
    token = m.group(0) if m else ("clean" if p.returncode == 0 else "failed")
    return {"exit": p.returncode, "token": token}


def main(a):
    repo = Path(a[0]).resolve() if a and not a[0].startswith("-") else Path.cwd()
    gates = propose(repo)
    if "--run" in a:
        for g in gates:
            if g["kind"] == "live":
                g["baseline"] = {"exit": None, "token": "not run: live gate, human owns it"}
                continue
            g["baseline"] = measure(repo, g)
    ev = next((g.get("runner_evidence") for g in gates if g.get("runner_evidence")), None)
    doc = {"repo": str(repo), "gates": gates, "measured": "--run" in a, "runner_evidence": ev}
    if "--json" in a:
        print(json.dumps(doc))
        return 0
    if not gates:
        print(f"detect_gates: nothing recognised in {repo}")
        return 1
    print(f"proposed gates for {repo} ({'measured' if '--run' in a else 'NOT measured — pass --run'})")
    if ev:
        print(f"  runner evidence: {ev}")
    for g in gates:
        base = g.get("baseline")
        tail = f"  → exit {base['exit']} — {base['token']}" if base else ""
        print(f"  {g['gate']:<11} {g['command']:<28} ({g['dir']}){tail}")
    if "--run" not in a:
        print("\nA gates table without measured baselines is a guess. Re-run with --run before using it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
