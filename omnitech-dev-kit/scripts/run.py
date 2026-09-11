#!/usr/bin/env python3
"""run.py — start ONE cost-guarded role run through a harness adapter and log spend.

usage: run.py <role> <unit> <cwd> [--config kit.config.json] [--harness omp|claude|codex|opencode]
              [--model M] [--thinking low|medium|high] [--spend-dir DIR]
              [--out FILE] [--validate packet|receipt|evidence] [--dry-run] -- <prompt parts...>

Guarantees (stdlib only):
- stdin is /dev/null so print mode never blocks; stdout+stderr go to <spend-dir>/runs/<ts>-<role>-<unit>.log
- wall clock enforced here (SIGKILL after role max_time + 30s grace) regardless of harness support
- key read from the env var named in config, never from dotfiles; never printed
- cost: usage_probe "openrouter" reads key usage before/after (configurable lag); "harness" reads the
  cost the adapter reports (claude); "none" records 0 and guards only wall clock
- one JSON line appended to <spend-dir>/spend.jsonl and one markdown row to <spend-dir>/spend.md
- hard guards: exit 3 if one run > run_cap_usd, exit 4 if campaign (cumulative - baseline) > campaign_cap_usd
- --out FILE copies the role's final answer to FILE (evidence note, packet draft, receipt), and
  --validate runs validate.py on it: a run whose artefact fails validation exits 5 (fail-closed)
- --dry-run prints the resolved adapter, env and prompt parts and exits 0 without spending
- never loops: one invocation = one run; a guard exit is a stop, not a retry signal
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
HARNESSES = ("omp", "claude", "codex", "opencode")

def die(msg, code=1):
    print(f"run.py: {msg}", file=sys.stderr); sys.exit(code)

def parse_time(s):
    s = str(s).strip()
    if s.endswith("m"): return int(float(s[:-1]) * 60)
    if s.endswith("s"): return int(float(s[:-1]))
    return int(s)

def load_config(path):
    for cand in [path, Path.cwd() / "kit.config.json", KIT.parent / "kit.config.json", KIT.parent / "kit.config.example.json"]:
        if cand and Path(cand).is_file():
            return json.loads(Path(cand).read_text()), Path(cand)
    die("no kit.config.json found")

def openrouter_usage(key):
    req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return float(json.load(r)["data"]["usage"])

def main(argv):
    if "--" not in argv: die(__doc__)
    i = argv.index("--"); head, prompt = argv[:i], argv[i + 1:]
    if len(head) < 3: die(__doc__)
    role, unit, cwd = head[0], head[1], Path(head[2]).resolve()
    if not cwd.is_dir(): die(f"cwd {cwd} is not a directory")
    opts = {"--config": None, "--harness": None, "--model": None, "--thinking": None, "--spend-dir": None,
            "--out": None, "--validate": None}
    flags = {"--dry-run": False}
    rest = head[3:]
    while rest:
        k = rest.pop(0)
        if k in flags: flags[k] = True; continue
        if k not in opts: die(f"unknown option {k}")
        if not rest: die(f"{k} needs a value")
        opts[k] = rest.pop(0)
    cfg, cfg_path = load_config(opts["--config"])
    harness = opts["--harness"] or cfg.get("harness", "omp")
    if harness not in HARNESSES: die(f"harness {harness!r} not in {HARNESSES}")
    roles = cfg.get("roles", {})
    if role not in roles: die(f"role {role!r} not in config roles {sorted(roles)}")
    rc = roles[role]
    model = opts["--model"] or (cfg.get("models", {}) or {}).get(role) or rc.get("model")
    thinking = opts["--thinking"] or rc.get("thinking")
    spend_dir = Path(opts["--spend-dir"] or cfg_path.parent).resolve()
    adapter = KIT / "harness" / f"{harness}.sh"
    if not adapter.is_file(): die(f"no adapter {adapter}")
    for p in prompt:
        if p.startswith("@") and not Path(p[1:]).is_file() and not (cwd / p[1:]).is_file():
            die(f"prompt file not found: {p[1:]}")

    ts = time.strftime("%Y%m%dT%H%M%S")
    log = spend_dir / "runs" / f"{ts}-{role}-{unit}.log"
    cost_file = spend_dir / "runs" / f"{ts}-{role}-{unit}.cost"
    env = dict(os.environ, KIT_ROLE=role, KIT_UNIT=unit, KIT_TOOLS=rc["tools"], KIT_MAX_TIME=rc["max_time"],
               KIT_APPROVAL=rc["approval"], KIT_PLUGIN_ROOT=str(KIT), KIT_COST_FILE=str(cost_file))
    if model: env["KIT_MODEL"] = model
    if thinking: env["KIT_THINKING"] = thinking
    if opts["--out"]: env["KIT_OUT"] = str(Path(opts["--out"]).resolve())
    for k, v in (cfg.get("harness_env", {}) or {}).get(harness, {}).items(): env[k] = str(v)
    limit = parse_time(rc["max_time"]) + 30

    if flags["--dry-run"]:
        shown = {k: v for k, v in env.items() if k.startswith("KIT_")}
        print(f"dry-run: {role}/{unit} harness={harness} cwd={cwd} limit={limit}s")
        print(f"  adapter: {adapter}")
        print("  env:", json.dumps(shown, indent=None))
        print("  prompt parts:"); [print(f"    {p if len(p) < 160 else p[:157] + '...'}") for p in prompt]
        print(f"  log: {log}")
        if opts["--validate"]: print(f"  validate: {opts['--validate']} {opts['--out']}")
        return 0

    (spend_dir / "runs").mkdir(parents=True, exist_ok=True)
    probe_mode = cfg.get("usage_probe", "openrouter")
    key = os.environ.get(cfg.get("key_env", "OPENROUTER_API_KEY"))
    probe = probe_mode == "openrouter" and bool(key)
    if probe_mode == "openrouter" and not key:
        print("run.py: usage_probe is openrouter but the key env var is unset; cost will be recorded as 0", file=sys.stderr)
    before = openrouter_usage(key) if probe else None

    start = time.time()
    with open(log, "wb") as lf, open(os.devnull, "rb") as devnull:
        lf.write(f"# kit run {ts} role={role} unit={unit} harness={harness} model={model or '-'} cwd={cwd}\n".encode())
        lf.flush()
        try:
            p = subprocess.run([str(adapter), *prompt], cwd=cwd, stdin=devnull, stdout=lf, stderr=subprocess.STDOUT, env=env, timeout=limit)
            rc_exit = p.returncode
        except subprocess.TimeoutExpired:
            rc_exit = 124
            lf.write(b"\nrun.py: killed at wall-clock limit\n")
    secs = int(time.time() - start)

    after = cost = None
    if probe:
        time.sleep(int(cfg.get("usage_lag_seconds", 12)))
        after = openrouter_usage(key)
        cost = round(after - before, 4)
    elif probe_mode == "harness" and cost_file.is_file():
        try: cost = round(float(cost_file.read_text().strip() or 0), 4)
        except ValueError: cost = None
    if cost_file.exists(): cost_file.unlink()

    validated = None
    if opts["--validate"]:
        if not opts["--out"]: die("--validate needs --out")
        kind = opts["--validate"]
        args = [sys.executable, str(HERE / "validate.py"), kind, opts["--out"]]
        if kind == "packet": args += ["--repo", str(cwd)]
        v = subprocess.run(args, capture_output=True, text=True)
        validated = v.returncode == 0
        with open(log, "ab") as lf: lf.write(f"\n# validate {kind}: exit {v.returncode}\n{v.stdout}{v.stderr}".encode())

    row = {"ts": ts, "role": role, "unit": unit, "harness": harness, "model": model or "", "seconds": secs,
           "exit": rc_exit, "cost_usd": cost if cost is not None else 0.0, "cumulative_usd": after,
           "validated": validated, "log": f"runs/{log.name}", "campaign": cfg.get("campaign", "")}
    with open(spend_dir / "spend.jsonl", "a") as f: f.write(json.dumps(row) + "\n")
    with open(spend_dir / "spend.md", "a") as f:
        f.write(f"| {ts} | {role} | {unit} | {secs}s | exit {rc_exit} | ${row['cost_usd']:.4f} | {after if after is not None else 'n/a'} | {row['log']} |\n")
    print(f"run: {role}/{unit} harness={harness} exit={rc_exit} time={secs}s cost=${row['cost_usd']:.4f} cumulative={after} "
          f"validated={validated} log={log}")

    if cost is not None and cost > float(cfg.get("run_cap_usd", 0.25)):
        die(f"GUARD: single run over ${cfg['run_cap_usd']}", 3)
    base = cfg.get("campaign_baseline_usd")
    if after is not None and base is not None and (after - float(base)) > float(cfg.get("campaign_cap_usd", 2.0)):
        die(f"GUARD: campaign spend over ${cfg['campaign_cap_usd']}", 4)
    if validated is False:
        die(f"artefact failed validation ({opts['--validate']}); see log", 5)
    sys.exit(rc_exit)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
