#!/usr/bin/env python3
"""gate_runner.py — run the declared gates deterministically and record what happened. Stdlib only.

usage: gate_runner.py <worktree> --gates gates.json [--scope selected|full] [--base REF]
                      [--include-live] [--out gates-run.json] [--receipt-lines] [--json]

Why this exists: a gate is a command with an exit code. It does not need a model, and a model should not
be the author of its result. Before this, a cheap worker shelled out to the test bar and then NARRATED
the outcome, which cost minutes of model time and produced a gate line that was, in the end, prose. Here
the kit runs the commands itself and records the exit code, the duration, a count token, the log path,
and a digest of the candidate that was tested. The model's job shrinks to the part that needs judgement:
reading the diff and deciding whether the new tests could ever fail.

Scope, and why the record carries it:
  selected  run only what the change can affect — the test files in the diff, plus the runner's own
            related-test mechanism for changed sources. Fast enough to run on every iteration.
  full      run each gate as declared. Slower, and the only scope that can support an ACCEPT.
An ACCEPT built on a `selected` run is not a coverage claim, so the scope travels with the record and
`--receipt-lines` marks a selected run in the line itself. Live gates (browser, e2e) are never run
without --include-live: they are human-owned by default.

The candidate digest binds the record to the exact content tested. Re-running the gates after any edit
produces a different digest, so a receipt can never be paired with a candidate it did not examine.
"""
import hashlib, json, re, shlex, subprocess, sys, time
from pathlib import Path

COUNT_RE = re.compile(r"(\d+)\s+(passed|passing|failed|tests?|findings?|errors?|problems?)", re.I)
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.py$|test_.*\.py$")
# A narrowed run that matches nothing means this gate's suite is untouched by the change. That is
# NOT-APPLICABLE, not a failure: reporting it as red trains people to ignore red.
NO_TESTS_RE = re.compile(
    r"No test files found|no tests ran|0 matches|matched 0 test|Pattern .* not found|"
    r"No tests found|testPathPattern.*0 matches", re.I)

# runner → how to narrow it. None means "this runner cannot be narrowed here; say so rather than pretend".
NARROWING = {
    "vitest":     "positional",   # vitest treats bare args as filename filters
    "jest":       "findRelated",
    "pytest":     "positional",
    "playwright": None,           # needs tags/grep the repo may not have; stays human-owned
    "unknown":    None,
}


def passed_count(token: str | None) -> int | None:
    """The 'N passed' figure from a count token, when there is one."""
    if not token:
        return None
    m = re.search(r"(\d+)\s+(passed|passing)", token, re.I)
    return int(m.group(1)) if m else None


def classify(rc: int, token: str, applicable: bool, baseline: str | None, scope: str = "full") -> tuple[str, str]:
    """(status, why). A gate that was ALREADY failing at baseline is not this change's regression, as
    long as it has not gone backwards. Reporting a known-red gate as this candidate's failure is how a
    team learns to ignore red."""
    if not applicable:
        return "not_applicable", "no matching tests for this change"
    if rc == 0:
        now, before = passed_count(token), passed_count(baseline)
        # A count comparison only means something at full scope: a narrowed run passes 7 of 7 and the
        # baseline says 674, and that is not a regression, it is a smaller run.
        if scope == "full" and now is not None and before is not None and now < before:
            return "regression", f"passing count fell: {before} → {now}"
        return "pass", ""
    now, before = passed_count(token), passed_count(baseline)
    baseline_red = bool(baseline) and ("failed" in baseline.lower() or passed_count(baseline) is not None
                                       and "exit 0" not in baseline)
    if now is not None and before is not None and now >= before and baseline_red:
        return "no_regression", (f"non-zero exit, but this gate was already failing at baseline and the "
                                 f"passing count held at {now} ≥ {before}")
    return "regression", f"exit {rc}" + (f"; baseline was {baseline!r}" if baseline else "")


def detect_runner(gate: dict) -> str:
    blob = f"{gate.get('script', '')} {gate.get('command', '')}".lower()
    for name in ("vitest", "jest", "playwright", "pytest"):
        if name in blob:
            return name
    return "unknown"


def changed_files(worktree: Path, base: str | None) -> list[str]:
    """Everything this candidate changes, staged or not, tracked or not."""
    out = set()
    for args in (["diff", "--name-only"], ["diff", "--name-only", "--cached"],
                 ["ls-files", "--others", "--exclude-standard"]):
        p = subprocess.run(["git", "-C", str(worktree), *args], capture_output=True, text=True)
        out.update(x for x in p.stdout.splitlines() if x.strip())
    if base:
        p = subprocess.run(["git", "-C", str(worktree), "diff", "--name-only", f"{base}...HEAD"],
                           capture_output=True, text=True)
        out.update(x for x in p.stdout.splitlines() if x.strip())
    return sorted(f for f in out if "node_modules/" not in f)


def candidate_digest(worktree: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        p = worktree / f
        h.update(f.encode())
        h.update(p.read_bytes() if p.is_file() else b"<absent>")
    return h.hexdigest()[:16]


def narrow(gate: dict, runner: str, changed: list[str], gate_dir: Path, worktree: Path):
    """(extra_args, why) for a selected run, or (None, why-not)."""
    how = NARROWING.get(runner)
    if how is None:
        return None, f"{runner} cannot be narrowed safely here"
    tests = [f for f in changed if TEST_PATH_RE.search(f)]
    srcs = [f for f in changed if f not in tests]
    # Paths in the gate's own working directory, which is what the runner will resolve against.
    def rel(f):
        try:
            return str((worktree / f).relative_to(gate_dir))
        except ValueError:
            return None
    if how == "positional":
        names = [Path(f).stem for f in tests if rel(f)]
        if names:
            return sorted(set(names)), f"{len(names)} changed test file(s) by name"
        if srcs:
            return None, "only sources changed and no test file names to filter on"
        return None, "nothing changed that this gate covers"
    if how == "findRelated":
        paths = [r for f in (tests + srcs) if (r := rel(f))]
        if paths:
            return ["--findRelatedTests", *paths], f"{len(paths)} changed file(s)"
        return None, "no changed files inside this gate's directory"
    return None, "no narrowing strategy"


def run_one(worktree: Path, gate: dict, scope: str, changed: list[str], logs: Path):
    gate_dir = (worktree / gate["dir"]).resolve()
    runner = detect_runner(gate)
    cmd = gate["command"]
    mode, why = "full", "declared command"
    if scope == "selected":
        extra, why = narrow(gate, runner, changed, gate_dir, worktree)
        if extra:
            # `npm run x -- args` forwards to the underlying runner; a bare command takes them directly.
            cmd = f"{gate['command']} -- {' '.join(shlex.quote(a) for a in extra)}" \
                if re.match(r"^(npm run|pnpm|yarn|bun run)\b", gate["command"]) else \
                f"{gate['command']} {' '.join(shlex.quote(a) for a in extra)}"
            mode = "selected"
        else:
            mode = "full"  # could not narrow; be honest and run it whole rather than skip silently

    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{gate['gate']}-{gate['dir'].replace('/', '_')}-{int(time.time())}.log"
    start = time.time()
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(gate_dir), capture_output=True, text=True, timeout=3600)
        rc, blob = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc, blob = 124, f"timed out after 3600s\n{e}"
    secs = round(time.time() - start, 1)
    log.write_text(blob)
    m = None
    for m in COUNT_RE.finditer(blob):
        pass
    token = m.group(0) if m else ("clean" if rc == 0 else "failed")
    applicable = True
    if mode == "selected" and (NO_TESTS_RE.search(blob) or re.search(r"\b0 (test|tests|passed)\b", token, re.I)):
        applicable, token = False, "no matching tests — this suite is untouched by the change"
    baseline_token = (gate.get("baseline") or {}).get("token")
    baseline_exit = (gate.get("baseline") or {}).get("exit")
    if baseline_exit not in (0, None) and baseline_token:
        baseline_token = f"{baseline_token} (baseline exit {baseline_exit})"
    status, status_why = classify(rc, token, applicable, baseline_token, mode)
    return {"gate": gate["gate"], "kind": gate["kind"], "dir": gate["dir"], "command": cmd,
            "declared": gate["command"], "runner": runner, "scope": mode, "why": why,
            "exit": rc, "seconds": secs, "token": token, "log": str(log), "applicable": applicable,
            "status": status, "status_why": status_why,
            "baseline": baseline_token, "baseline_exit": baseline_exit}


def receipt_line(r: dict) -> str:
    if r["status"] == "not_applicable":
        return f"gate: {r['declared']} ({r['dir']}) → exit 0 — not applicable: {r['token']}"
    if r["status"] == "no_regression":
        return (f"gate: {r['command']} ({r['dir']}) → exit {r['exit']} — {r['token']} "
                f"[pre-existing failure, not this change: {r['status_why']}]")
    mark = "" if r["scope"] == "full" else f" [SELECTED: {r['why']} — not a full-bar claim]"
    return f"gate: {r['command']} ({r['dir']}) → exit {r['exit']} — {r['token']}{mark}"


def main(a):
    if not a or a[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    worktree = Path(a[0]).resolve()
    if not worktree.is_dir():
        print(f"gate_runner: {worktree} is not a directory", file=sys.stderr)
        return 2
    gpath = Path(a[a.index("--gates") + 1]) if "--gates" in a else worktree / "gates.json"
    if not gpath.is_file():
        print(f"gate_runner: no gates file at {gpath}; run detect_gates.py --run first", file=sys.stderr)
        return 2
    scope = a[a.index("--scope") + 1] if "--scope" in a else "selected"
    if scope not in ("selected", "full"):
        print("gate_runner: --scope must be selected or full", file=sys.stderr)
        return 2
    base = a[a.index("--base") + 1] if "--base" in a else None
    gates = json.loads(gpath.read_text()).get("gates", [])
    live = [g for g in gates if g["kind"] == "live"]
    runnable = gates if "--include-live" in a else [g for g in gates if g["kind"] != "live"]

    # Dedupe: two `unit` gates in one directory (e.g. `npm run test` and `npm run test:product`) are the same
    # suite run twice, ~100 s each. Keep the one green at baseline; the other is superseded, not run.
    by_key = {}
    for g in runnable:
        by_key.setdefault((g["dir"], g["gate"]), []).append(g)   # by LABEL: rail is not unit
    superseded = []
    for key, group in by_key.items():
        if len(group) > 1:
            green = [g for g in group if (g.get("baseline") or {}).get("exit") == 0]
            keep = green[0] if green else group[0]
            superseded += [g for g in group if g is not keep]
    runnable = [g for g in runnable if g not in superseded]
    changed = changed_files(worktree, base)
    digest = candidate_digest(worktree, changed)
    logs = worktree.parent / f".kit-gate-logs-{worktree.name}"
    results = [run_one(worktree, g, scope, changed, logs) for g in sorted(runnable, key=lambda g: g["rank"])]

    failed = [r for r in results if r["status"] == "regression"]
    not_applicable = [r for r in results if r["status"] == "not_applicable"]
    tolerated = [r for r in results if r["status"] == "no_regression"]
    selected = [r for r in results if r["scope"] == "selected"]
    doc = {
        "worktree": str(worktree), "scope": scope, "candidate_digest": digest,
        "changed_files": changed, "ran": len(results), "failed": len(failed),
        "selected_runs": len(selected), "not_applicable": len(not_applicable),
        "pre_existing_failures": len(tolerated),
        "acceptance_eligible": scope == "full" and not failed,
        "live_not_run": [f"{g['command']} ({g['dir']})" for g in live] if "--include-live" not in a else [],
        "superseded": [f"{g['command']} ({g['dir']})" for g in superseded],
        "results": results,
    }
    out = a[a.index("--out") + 1] if "--out" in a else None
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(doc, indent=2) + "\n")

    if "--json" in a:
        print(json.dumps(doc))
    elif "--receipt-lines" in a:
        for r in results:
            print(receipt_line(r))
    else:
        print(f"gates: scope={scope} candidate={digest} changed={len(changed)} file(s)")
        for r in results:
            mark = {"pass": "ok  ", "not_applicable": "n/a ", "no_regression": "was ", "regression": "FAIL"}[r["status"]]
            s = "" if r["scope"] == "full" else f"  [selected: {r['why']}]"
            extra = f"  ({r['status_why']})" if r["status_why"] else ""
            print(f"  {mark}  {r['gate']:<11} {r['seconds']:>6.1f}s  exit {r['exit']:<3} {r['token']}{s}{extra}")
        for g in doc["live_not_run"]:
            print(f"  --    live gate not run (human owns it): {g}")
        for g in doc["superseded"]:
            print(f"  --    superseded (same suite as another unit gate here): {g}")
        if not doc["acceptance_eligible"]:
            why = "a gate failed" if failed else f"scope is {scope}, and only a full run can support an ACCEPT"
            print(f"\nNOT acceptance-eligible: {why}.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
