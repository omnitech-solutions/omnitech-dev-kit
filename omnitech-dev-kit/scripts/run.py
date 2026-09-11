#!/usr/bin/env python3
"""run.py — start ONE cost-guarded role run through a harness adapter and log spend.

usage: run.py <role> <unit> <cwd> [--config kit.config.json] [--harness omp|claude]
              [--model M] [--thinking low|medium|high] [--spend-dir DIR] -- <prompt parts...>

Guarantees (stdlib only):
- stdin is /dev/null so print mode never blocks; stdout+stderr go to <spend-dir>/runs/<ts>-<role>-<unit>.log
- wall clock enforced here (SIGKILL after role max_time + 30s grace) regardless of harness support
- key read from the env var named in config, never from dotfiles; never printed
- OpenRouter key usage probed before/after (configurable lag); one JSON line appended to <spend-dir>/spend.jsonl
  and one markdown row to <spend-dir>/spend.md
- hard guards: exit 3 if one run > run_cap_usd, exit 4 if campaign (cumulative - baseline) > campaign_cap_usd
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent

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
    opts = {"--config": None, "--harness": None, "--model": None, "--thinking": None, "--spend-dir": None}
    rest = head[3:]
    while rest:
        k = rest.pop(0)
        if k not in opts: die(f"unknown option {k}")
        opts[k] = rest.pop(0)
    cfg, cfg_path = load_config(opts["--config"])
    harness = opts["--harness"] or cfg.get("harness", "omp")
    roles = cfg.get("roles", {})
    if role not in roles: die(f"role {role!r} not in config roles {sorted(roles)}")
    rc = roles[role]
    spend_dir = Path(opts["--spend-dir"] or cfg_path.parent).resolve()
    (spend_dir / "runs").mkdir(parents=True, exist_ok=True)
    adapter = KIT / "harness" / f"{harness}.sh"
    if not adapter.is_file(): die(f"no adapter {adapter}")

    key = os.environ.get(cfg.get("key_env", "OPENROUTER_API_KEY"))
    probe = cfg.get("usage_probe") == "openrouter" and key
    before = openrouter_usage(key) if probe else None

    ts = time.strftime("%Y%m%dT%H%M%S")
    log = spend_dir / "runs" / f"{ts}-{role}-{unit}.log"
    env = dict(os.environ, KIT_TOOLS=rc["tools"], KIT_MAX_TIME=rc["max_time"], KIT_APPROVAL=rc["approval"],
               KIT_PLUGIN_ROOT=str(KIT))
    if opts["--model"]: env["KIT_MODEL"] = opts["--model"]
    if opts["--thinking"]: env["KIT_THINKING"] = opts["--thinking"]
    limit = parse_time(rc["max_time"]) + 30
    start = time.time()
    with open(log, "wb") as lf, open(os.devnull, "rb") as devnull:
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
    row = {"ts": ts, "role": role, "unit": unit, "harness": harness, "model": opts["--model"] or "", "seconds": secs,
           "exit": rc_exit, "cost_usd": cost if cost is not None else 0.0, "cumulative_usd": after, "log": f"runs/{log.name}"}
    with open(spend_dir / "spend.jsonl", "a") as f: f.write(json.dumps(row) + "\n")
    with open(spend_dir / "spend.md", "a") as f:
        f.write(f"| {ts} | {role} | {unit} | {secs}s | exit {rc_exit} | ${row['cost_usd']:.4f} | {after if after is not None else 'n/a'} | {row['log']} |\n")
    print(f"run: {role}/{unit} harness={harness} exit={rc_exit} time={secs}s cost=${row['cost_usd']:.4f} cumulative={after} log={log}")

    if cost is not None and cost > float(cfg.get("run_cap_usd", 0.25)):
        die(f"GUARD: single run over ${cfg['run_cap_usd']}", 3)
    base = cfg.get("campaign_baseline_usd")
    if after is not None and base is not None and (after - float(base)) > float(cfg.get("campaign_cap_usd", 2.0)):
        die(f"GUARD: campaign spend over ${cfg['campaign_cap_usd']}", 4)
    sys.exit(rc_exit)

if __name__ == "__main__":
    main(sys.argv[1:])
