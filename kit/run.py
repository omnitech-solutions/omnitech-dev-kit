#!/usr/bin/env python3
"""run.py — start ONE cost-guarded role run through a harness adapter and log spend.

usage: run.py <role> <unit> <cwd> [--config config.json] [--harness omp|claude|codex|opencode]
              [--model M] [--thinking low|medium|high] [--spend-dir DIR]
              [--out FILE | --artifact FILE] [--validate packet|receipt|evidence] [--max-time 8m]
              [--prefetch f1,f2,f3] [--dry-run] -- <prompt parts...>

Guarantees (stdlib only):
- stdin is /dev/null so print mode never blocks; stdout+stderr go to <spend-dir>/runs/<ts>-<role>-<unit>.log
- wall clock enforced here (SIGKILL after role max_time + 30s grace) regardless of harness support
- key read from the env var named in config, never from dotfiles; never printed
- cost: usage_probe "openrouter" reads key usage before/after (configurable lag); "harness" reads the
  cost the adapter reports (claude); "none" records 0 and guards only wall clock
- one JSON line appended to <spend-dir>/spend.jsonl and one markdown row to <spend-dir>/spend.md
- --prefetch inlines the named files (line-numbered) into the prompt and DISABLES TOOLS for the run. A
  read-only role does not need to explore: the human already knows which files the question is about. One
  turn means the context is submitted once instead of once per tool call, which is where the money goes.
- projected cost: when `model_prices` declares a model's rates, the run is costed before launch from the
  measured prompt size and the role's expected turns, and refused (exit 10) if the projection exceeds
  run_cap_usd. It is an estimate, and it is labelled as one.
- context pre-flight: when config.json declares the model's window in `model_context`, the prompt is
  measured before the run and refused (exit 6) if it would use more than `prompt_budget_fraction` of it.
  An over-window prompt is truncated by the runtime, the instructions are the part that disappears, and the
  model then loops on one tool call until the wall clock kills it. Cheaper to refuse than to watch.
- loop detection: a watchdog polls the log during the run and kills it (exit 125) once one tool call has
  repeated `loop_watchdog.repeat_threshold` times, instead of letting it burn the whole cap; after every run
  the log is analysed (scripts/analyze_run.py) and `loop_suspected`/`distinct_tools`/`loop_killed` go into
  the spend row. A looping run is never re-run unchanged.
- hard guards: exit 3 if one run > run_cap_usd, exit 4 if campaign (cumulative - baseline) > campaign_cap_usd
- --out FILE copies the role's final answer to FILE. Use it when the ANSWER is the artefact.
- --artifact FILE validates a file the MODEL wrote itself, without overwriting it. Use it whenever the
  prompt tells the model where to write: --out would clobber that file with the stdout stream, which is
  how a real verifier receipt was once replaced by a half-finished sentence.
- --validate runs validate.py on whichever of the two was given: a run whose artefact fails validation
  exits 5 (fail-closed)
- --max-time overrides the role's wall clock for one run (local models are slower than hosted ones);
  it never raises a dollar cap, only the clock
- --dry-run prints the resolved adapter, env and prompt parts and exits 0 without spending
- never loops: one invocation = one run; a guard exit is a stop, not a retry signal
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
HARNESSES = ("omp", "claude", "codex", "opencode")
CHARS_PER_TOKEN = 4  # deliberately crude; the guard is an order-of-magnitude check, not a tokenizer

def project_cost(cfg, model, prompt_tokens, turns, out_tokens=1200):
    """Rough pre-launch cost. An agent turn resubmits the whole conversation, so N turns cost about
    N*(N+1)/2 times one prompt in the worst case and N times in the common case; we use N times, which
    already showed 17x token amplification on a real 7-turn run. Returns (usd, basis) or (None, why)."""
    prices = (cfg.get("model_prices") or {})
    row = None
    for k, v in prices.items():
        if not isinstance(v, dict): continue
        if model == k or (k.endswith("*") and model and model.startswith(k[:-1])):
            if row is None or len(k) > row[0]: row = (len(k), v)
    if row is None: return None, f"no price declared for {model!r}"
    r = row[1]
    usd = (prompt_tokens * turns * float(r.get("in_per_mtok", 0)) + out_tokens * float(r.get("out_per_mtok", 0))) / 1e6
    return round(usd, 4), f"{prompt_tokens} prompt tokens x {turns} turn(s) + ~{out_tokens} out"

def estimate_tokens(parts, cwd):
    """Rough prompt size in tokens: @files are inlined by most adapters, text is passed through."""
    chars = 0
    for p in parts:
        if p.startswith("@"):
            f = Path(p[1:])
            f = f if f.is_file() else (Path(cwd) / p[1:])
            if f.is_file(): chars += f.stat().st_size
        else:
            chars += len(p)
    return chars // CHARS_PER_TOKEN

def model_window(cfg, model):
    """Declared context window for this model id, longest-prefix match, or None."""
    table = cfg.get("model_context") or {}
    if not model: return None
    best = None
    for k, v in table.items():
        if model == k or (k.endswith("*") and model.startswith(k[:-1])):
            if best is None or len(k) > best[0]: best = (len(k), v)
    return best[1] if best else None

def die(msg, code=1):
    print(f"run.py: {msg}", file=sys.stderr); sys.exit(code)

def parse_time(s):
    s = str(s).strip()
    if s.endswith("m"): return int(float(s[:-1]) * 60)
    if s.endswith("s"): return int(float(s[:-1]))
    return int(s)

def load_config(path):
    """An explicitly named config must exist. Falling back to another file — least of all the shipped
    example — would run the campaign under caps and models nobody chose."""
    if path:
        f = Path(path)
        if not f.is_file(): die(f"--config {path} does not exist (no fallback is used for an explicit config)", 2)
        return json.loads(f.read_text()), f.resolve()
    for cand in [Path.cwd() / "config.json", KIT / "templates" / "config.json"]:
        if cand.is_file():
            if cand.parent.name == "templates":
                print(f"run.py: using the template config — copy it into a campaign and pass --config", file=sys.stderr)
            return json.loads(cand.read_text()), cand.resolve()
    die("no config.json found; pass --config <campaign>/config.json")

def campaign_spent(spend_dir, campaign):
    """Durable campaign total from this campaign's own spend rows. Works for every cost source, including
    harness-reported costs, where a provider usage probe says nothing. Unknown costs are excluded from the
    total and reported separately so 'unknown' never reads as 'free'."""
    total, unknown = 0.0, 0
    f = Path(spend_dir) / "spend.jsonl"
    if not f.is_file(): return total, unknown
    for line in f.read_text().splitlines():
        if not line.strip(): continue
        try: r = json.loads(line)
        except Exception: continue
        if campaign and r.get("campaign") not in (campaign, None, ""): continue
        if r.get("cost_known") is False: unknown += 1
        else: total += float(r.get("cost_usd") or 0)
    return round(total, 4), unknown

# What each harness can actually ENFORCE, as opposed to what it can be asked politely to do.
# "no_shell": the role's tool list excludes bash and the harness can make shell unavailable.
# "no_write": the harness can make the workspace unwritable.
# "no_session": the harness can run without persisting a session.
HARNESS_CAPS = {
    "omp":      {"no_shell": True,  "no_write": True,  "no_session": True},
    "claude":   {"no_shell": True,  "no_write": True,  "no_session": True},
    # Codex has no tool allow-list: a read-only sandbox stops writes and network, but the model can still
    # run shell commands to read files. Verified live 2026-09-10: a reader role with tools=read,grep,glob
    # executed /bin/zsh -lc 'cat -n ...'.
    "codex":    {"no_shell": False, "no_write": True,  "no_session": True},
    # OpenCode restricts tools through the role agent file, not the CLI; sessions always persist.
    "opencode": {"no_shell": True,  "no_write": True,  "no_session": False},
}

def kill_tree(proc, grace=5):
    """Terminate the adapter's whole process group and confirm it is gone. subprocess.kill() only signals
    the wrapper; the model CLI it spawned survives, keeps generating and keeps billing."""
    import signal
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError): break
        try:
            proc.wait(timeout=grace); break
        except subprocess.TimeoutExpired:
            continue
    try: proc.wait(timeout=grace)
    except subprocess.TimeoutExpired: pass
    try:
        os.killpg(os.getpgid(proc.pid), 0)
        return False  # group still present; report honestly rather than assume
    except (ProcessLookupError, PermissionError):
        return True

def openrouter_usage(key):
    # Test hook: a file supplied this way stands in for the provider, so admission logic that probes
    # usage can be exercised without a key or a network call. Never set it in a real environment.
    pf = os.environ.get("KIT_USAGE_PROBE_FILE")
    if pf:
        return float(Path(pf).read_text().strip())
    req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return float(json.load(r)["data"]["usage"])

UNMEASURED_ANOMALY = "unmeasured cost on a paid model: the request may never have reached it"

def reconcile_lagged_cost(spend_dir, before):
    """OpenRouter usage reporting can lag past a run's whole probe backoff: the run is booked with
    cost_known=false and a false unmeasured-cost anomaly, while the dollars silently arrive in the
    next admission probe's cumulative total. Attribute that delta back to the earlier run, clear the
    false anomaly, and rewrite the ledger in place. Anything ambiguous (no probe, no delta) changes
    nothing: a reconciliation must never invent a cost."""
    if before is None:
        return
    f = Path(spend_dir) / "spend.jsonl"
    if not f.is_file():
        return
    rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    if not rows:
        return
    last = rows[-1]
    if last.get("cost_known") or last.get("cumulative_usd") is None:
        return
    delta = round(float(before) - float(last["cumulative_usd"]), 4)
    if delta <= 0:
        return
    last["cost_usd"] = delta
    last["cost_known"] = True
    last["reconciled"] = True
    last["anomalies"] = [a for a in (last.get("anomalies") or []) if a != UNMEASURED_ANOMALY]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    rec = Path(spend_dir) / "runs" / f"{last.get('ts')}-{last.get('role')}-{last.get('unit')}.run.json"
    if rec.is_file():
        try:
            rec.write_text(json.dumps(last, indent=2) + "\n")
        except Exception:
            pass
    print(f"run.py: reconciled lagged cost ${delta:.4f} for {last.get('role')}/{last.get('unit')}", file=sys.stderr)

def main(argv):
    if "--" not in argv: die(__doc__)
    i = argv.index("--"); head, prompt = argv[:i], argv[i + 1:]
    opts = {"--config": None, "--harness": None, "--model": None, "--thinking": None, "--spend-dir": None,
            "--out": None, "--validate": None, "--max-time": None, "--prefetch": None, "--artifact": None}
    flags = {"--dry-run": False, "--no-preamble": False, "--no-advice": False}
    # Options may appear anywhere before the `--`, not only after the positionals, so a wrapper can
    # prepend --config without the caller having to know where run.py wants it.
    positional, rest = [], list(head)
    while rest:
        k = rest.pop(0)
        if k in flags: flags[k] = True; continue
        if k in opts:
            if not rest: die(f"{k} needs a value")
            opts[k] = rest.pop(0); continue
        if k.startswith("--"): die(f"unknown option {k}")
        positional.append(k)
    if len(positional) < 2: die(__doc__)
    role, unit = positional[0], positional[1]
    # cwd is optional: a wrapper already runs us in the right directory.
    cwd = Path(positional[2] if len(positional) > 2 else ".").resolve()
    if not cwd.is_dir(): die(f"cwd {cwd} is not a directory")
    if opts["--validate"] and not (opts["--out"] or opts["--artifact"]):
        die("--validate needs --out or --artifact (there would be no artefact to validate)", 2)
    if opts["--out"] and opts["--artifact"]:
        die("--out and --artifact are mutually exclusive: one captures the answer, the other checks a "
            "file the model wrote", 2)
    if opts["--validate"] and opts["--validate"] not in ("packet", "receipt", "evidence"):
        die(f"--validate {opts['--validate']!r} is not packet|receipt|evidence", 2)
    cfg, cfg_path = load_config(opts["--config"])
    harness = opts["--harness"] or cfg.get("harness", "omp")
    if harness not in HARNESSES: die(f"harness {harness!r} not in {HARNESSES}")
    roles = cfg.get("roles", {})
    if role not in roles: die(f"role {role!r} not in config roles {sorted(roles)}")
    rc = dict(roles[role])
    if opts["--max-time"]: rc["max_time"] = opts["--max-time"]
    model = opts["--model"] or (cfg.get("models", {}) or {}).get(role) or rc.get("model")
    allowed = cfg.get("allowed_model_prefixes") or ["openrouter/", "z-ai/", "claude-"]
    local_prefixes = ("lmstudio/", "lm-studio/", "ollama/", "local/")
    if model and not any(model.startswith(pfx) for pfx in allowed):
        if model.startswith(local_prefixes) and not cfg.get("allow_local_models", False):
            die(f"MODEL: {model!r} is a local model and allow_local_models is not true in config.json. "
                f"Local models are never a default here: they run at zero measured cost, small windows, and no "
                f"way to tell a wasted run from a cheap one. Opt in explicitly if you mean it.", 11)
        if not model.startswith(local_prefixes):
            die(f"MODEL: {model!r} is not under allowed_model_prefixes {allowed}. Add the prefix to config.json "
                f"deliberately, or pick an allowed model.", 11)
    if not model and not flags.get("--dry-run"):
        # Letting the harness pick its own default once routed a planner onto a local 8K-context model:
        # a 489-second run that produced no plan, at a cost the probe could not even see.
        die(f"MODEL: no model resolved for role {role!r} (not in config.json models, not in the role, "
            f"no --model). The harness would silently use its own default. Refusing.", 11)
    thinking = opts["--thinking"] or rc.get("thinking")
    spend_dir = Path(opts["--spend-dir"] or cfg_path.parent).resolve()
    adapter = KIT / "harness" / f"{harness}.sh"
    if not adapter.is_file(): die(f"no adapter {adapter}")
    # Session and daily caps read the MACHINE ledger at $KIT_HOME, never this campaign's spend.jsonl.
    # A campaign cap cannot see a bad afternoon spread across campaigns: two campaigns in one session
    # each got their own budget and the cap silently did not bind (found by audit 2026-09-12).
    # run.py is executed as a script, so put the kit root on sys.path and import the real package.
    # Path-loading a single module breaks its own relative imports; a swallowed ImportError is how a
    # cap silently stops guarding, so this import is deliberate and unguarded.
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))
    from kit.settings import load as load_settings
    _s, _prov = load_settings(spend_dir, facts={"role": role, "harness": harness, "unit": unit,
                                                "model": model, "campaign": cfg.get("campaign"),
                                                "repo": Path(cwd).name,
                                                "session": os.environ.get("KIT_SESSION_ID")})
    from kit import home as kit_home
    _caps = _s.get("caps") or {}
    _sid = kit_home.session_id()
    # A machine-level halt stops every campaign everywhere, not just this one.
    if (_m := kit_home.halted()):
        die("HALTED at $KIT_HOME: " + "; ".join(_m.get("reasons", [])) +
            "\n  Every campaign on this machine is stopped. Read why, then: kit resume --machine", 4)
    for _key, _label, _spent in (
            ("session_usd", f"session {_sid}", kit_home.spent(_sid)),
            ("daily_usd", f"today ({time.strftime('%Y-%m-%d')})",
             kit_home.spent(since_day=time.strftime("%Y%m%d")))):
        _limit = _caps.get(_key)
        if _limit and _spent >= float(_limit):
            kit_home.halt([f"{_label} spent ${_spent:.4f} of its ${float(_limit):.2f} cap (caps.{_key})"],
                          {"role": role, "unit": unit, "model": model})
            die(f"BUDGET: {_label} has spent ${_spent:.4f} of its ${float(_limit):.2f} cap "
                f"(caps.{_key}, set by {_prov.get('caps.' + _key, 'default')}). Nothing was launched. "
                f"Raise it deliberately, or `kit resume --machine` once you have decided.", 4)

    # WHO-YOU-ARE goes first in every prompt. It is the owner's standing instruction to every model the kit
    # runs, including whoever orchestrates: verify before asserting, read before inferring, never defer,
    # write learnings down now. Only --no-preamble removes it, and that is deliberate friction.
    preamble = KIT / "promptbooks" / "WHO-YOU-ARE.md"
    if not flags["--no-preamble"] and preamble.is_file() and f"@{preamble}" not in prompt:
        prompt = [f"@{preamble}"] + list(prompt)
    # Resolve every @file to an ABSOLUTE path here. Pre-flight used to accept a file relative to the
    # caller while the adapter resolved it relative to the run's cwd — so a campaign folder that is
    # gitignored (and therefore absent from a fresh worktree) passed the check and was then unreadable.
    # Only input paths become absolute; receipt paths named in the instruction text stay worktree-relative.
    resolved = []
    for part in prompt:
        if part.startswith("@"):
            raw = part[1:]
            cand = next((c for c in (Path(raw), Path.cwd() / raw, cwd / raw) if c.is_file()), None)
            if cand is None:
                die(f"prompt file not found from the caller ({Path.cwd()}) or the run cwd ({cwd}): {raw}")
            resolved.append("@" + str(cand.resolve()))
        else:
            resolved.append(part)
    prompt = resolved
    # Capability contract. A boundary the harness cannot enforce is not a boundary, so a gap in what the
    # ROLE is allowed to touch refuses the run. Session persistence is recorded as a warning instead: it
    # weakens reproducibility and leaves history behind, but it cannot let a role exceed its scope.
    # --prefetch: inline the named files and take the tools away. This is the single biggest cost lever
    # on harnesses that bill per turn, because the conversation is submitted once instead of once per call.
    prefetch_files = [f.strip() for f in (opts["--prefetch"] or "").split(",") if f.strip()]
    if prefetch_files:
        blocks = []
        for f in prefetch_files:
            c = next((x for x in (Path(f), Path.cwd() / f, cwd / f) if x.is_file()), None)
            if c is None: die(f"--prefetch file not found: {f}")
            numbered = "\n".join(f"{i:5d}  {l}" for i, l in enumerate(c.read_text().splitlines(), 1))
            blocks.append(f"### {f} (complete, line-numbered)\n\n```\n{numbered}\n```")
        prompt = prompt[:-1] + blocks + [prompt[-1]] if len(prompt) > 1 else blocks + prompt
        prompt.append(
            "Every file you need is supplied above in full. You have no tools; do not ask to read anything. "
            "Cite each fact as path:line, for example src/thing.ts:42 — never 'at line 42'. "
            "Output ONLY the artefact your instructions name, in exactly the shape they prescribe, with no "
            "preamble before its first line.")
        rc = dict(rc); rc["tools"] = ""; rc["writes"] = False
        tools = set()

    caps = HARNESS_CAPS.get(harness, {})
    tools = {t.strip() for t in rc["tools"].split(",") if t.strip()}
    if prefetch_files and harness in ("codex",):
        msg = (f"{harness} cannot disable its tools, so a no-tools prefetch run cannot be guaranteed there "
               f"(the model may still shell out even with every file supplied)")
        if not any(a and a in msg for a in ((cfg.get("allow_capability_gap") or {}).get(harness, []))):
            die(f"PREFETCH: {msg}. Use omp or claude for a guaranteed prefetch run, drop --prefetch and accept "
                f"the turn cost, or record this gap in allow_capability_gap.{harness}.", 7)
        print(f"run.py: CAPABILITY WARNING — {msg} (gap accepted in config)", file=sys.stderr)
    gaps, warns = [], []
    if "bash" not in tools and not caps.get("no_shell", False):
        gaps.append(f"role {role!r} excludes bash but {harness} cannot make shell unavailable")
    if not rc.get("writes", "edit" in tools or "write" in tools) and not caps.get("no_write", False):
        gaps.append(f"role {role!r} must not write but {harness} cannot enforce that")
    if not caps.get("no_session", False):
        warns.append(f"{harness} always persists a session; the no-session part of the contract is not met")
    allowed_gaps = [a for a in (cfg.get("allow_capability_gap") or {}).get(harness, []) if isinstance(a, str)]
    blocking = [g for g in gaps if not any(a and a in g for a in allowed_gaps)]
    for w in warns: print(f"run.py: CAPABILITY WARNING — {w}", file=sys.stderr)
    if blocking and not flags["--dry-run"]:
        die("CAPABILITY: " + "; ".join(blocking) +
            f". A boundary the harness cannot enforce is not a boundary. Use a harness that can enforce it, "
            f"or record the accepted gap explicitly in config.json under allow_capability_gap.{harness} "
            f"as a substring of this message.", 7)

    if role == "implementer" and not flags["--dry-run"]:
        try:
            common = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                    capture_output=True, text=True, timeout=15).stdout.strip()
            gitdir = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-dir"],
                                    capture_output=True, text=True, timeout=15).stdout.strip()
            if common and gitdir and Path(common) == Path(gitdir):
                die(f"WORKTREE: {cwd} is the primary checkout. An implementer runs in a throwaway worktree "
                    f"(git worktree add -b unit/<id> ../wt-<id> <branch>), never here.", 8)
        except subprocess.SubprocessError:
            pass

    est = estimate_tokens(prompt, cwd)
    window = model_window(cfg, model)
    frac = float(cfg.get("prompt_budget_fraction", 0.5))
    budget = int(window * frac) if window else None

    ts = time.strftime("%Y%m%dT%H%M%S")
    log = spend_dir / "runs" / f"{ts}-{role}-{unit}.log"
    cost_file = spend_dir / "runs" / f"{ts}-{role}-{unit}.cost"
    writes = bool(rc.get("writes", "edit" in tools or "write" in tools))
    env = dict(os.environ, KIT_ROLE=role, KIT_UNIT=unit, KIT_TOOLS=rc["tools"], KIT_MAX_TIME=rc["max_time"],
               KIT_APPROVAL=rc["approval"], KIT_PLUGIN_ROOT=str(KIT), KIT_COST_FILE=str(cost_file),
               KIT_WRITES="1" if writes else "0",
               KIT_NO_TOOLS="1" if prefetch_files else "0")
    per_run_cap = float(cfg.get("run_cap_usd", 0.25))
    env["KIT_MAX_BUDGET_USD"] = str(per_run_cap)
    if model: env["KIT_MODEL"] = model
    if thinking: env["KIT_THINKING"] = thinking
    if opts["--out"]: env["KIT_OUT"] = str(Path(opts["--out"]).resolve())
    for k, v in (cfg.get("harness_env", {}) or {}).get(harness, {}).items(): env[k] = str(v)
    limit = parse_time(rc["max_time"]) + 30

    expected_turns = 1 if prefetch_files else int(rc.get("expected_turns", 8))
    proj, basis = project_cost(cfg, model, est, expected_turns)
    if proj is not None and not flags["--dry-run"] and proj > per_run_cap:
        die(f"PROJECTED COST: about ${proj:.4f} ({basis}) exceeds the ${per_run_cap} per-run cap for {model}. "
            f"This is an estimate, not a quote. Reduce the prompt, use --prefetch to collapse the turns, "
            f"choose a cheaper model, or raise run_cap_usd deliberately.", 10)

    # usage_probe may be one string or a {harness: mode} map — a Claude run must not be measured by an
    # OpenRouter delta, and an OpenRouter run has no harness-reported cost.
    _probe_cfg = cfg.get("usage_probe", "openrouter")
    probe_mode = _probe_cfg.get(harness, _probe_cfg.get("default", "none")) if isinstance(_probe_cfg, dict) else _probe_cfg
    key = os.environ.get(cfg.get("key_env", "OPENROUTER_API_KEY"))
    probe = probe_mode == "openrouter" and bool(key)
    # Admission, including the lagged-cost reconciliation of the previous run, runs on every admission
    # path, dry-run included. A real --dry-run still never touches the network: the probe fires only
    # with a key on a live run, or when the KIT_USAGE_PROBE_FILE test hook supplies the reading.
    stubbed = bool(os.environ.get("KIT_USAGE_PROBE_FILE"))
    before = openrouter_usage(key) if (probe and not flags["--dry-run"]) or stubbed else None
    reconcile_lagged_cost(spend_dir, before)
    if flags["--dry-run"]:
        shown = {k: v for k, v in env.items() if k.startswith("KIT_")}
        print(f"dry-run: {role}/{unit} harness={harness} cwd={cwd} limit={limit}s")
        print(f"  adapter: {adapter}")
        print("  env:", json.dumps(shown, indent=None))
        print("  prompt parts:"); [print(f"    {p if len(p) < 160 else p[:157] + '...'}") for p in prompt]
        if proj is not None: print(f"  projected cost: ~${proj:.4f} ({basis}); per-run cap ${per_run_cap}")
        if prefetch_files: print(f"  prefetch: {len(prefetch_files)} file(s) inlined, tools DISABLED, 1 turn")
        print(f"  prompt: ~{est} tokens" + (f" of a {window}-token window (budget {budget})" if window else " (no window declared for this model)"))
        print(f"  log: {log}")
        if opts["--validate"]: print(f"  validate: {opts['--validate']} {opts['--out']}")
        return 0

    if budget is not None and est > budget:
        die(f"CONTEXT: prompt ~{est} tokens exceeds {int(frac*100)}% of the {window}-token window for {model}. "
            f"The runtime would truncate it, the instructions would be what disappears, and the model would loop. "
            f"Shrink the prompt (fewer @files, narrower question), raise model_context if the window is wrong, "
            f"or choose a model with a larger window.", 6)
    (spend_dir / "runs").mkdir(parents=True, exist_ok=True)
    if probe_mode == "openrouter" and not key:
        if not cfg.get("allow_unmetered", False):
            die(f"METERING: usage_probe is 'openrouter' for {harness} but ${cfg.get('key_env', 'OPENROUTER_API_KEY')} "
                f"is not set, so this run could not be measured and would be recorded as $0.00. Export the key, "
                f"set usage_probe for this harness to 'harness' or 'none', or set allow_unmetered: true to accept "
                f"unmeasured spend deliberately.", 9)
        print("run.py: allow_unmetered — this run's cost will be recorded as UNKNOWN, not $0", file=sys.stderr)

    # Campaign admission BEFORE launching. The old per-run/per-campaign checks ran after the model had
    # already been paid for; an over-budget campaign could still start one more run. This refuses first.
    campaign = cfg.get("campaign", "")
    cap = cfg.get("campaign_cap_usd")
    spent_local, unknown_runs = campaign_spent(spend_dir, campaign)
    baseline = cfg.get("campaign_baseline_usd")
    spent = spent_local
    if before is not None and baseline is not None:
        spent = max(spent_local, round(float(before) - float(baseline), 4))
    if cap is not None and spent >= float(cap):
        die(f"BUDGET: campaign {campaign!r} has already spent ${spent:.4f} of its ${float(cap):.2f} cap"
            + (f" ({unknown_runs} run(s) of unknown cost are excluded)" if unknown_runs else "")
            + ". Nothing was launched. Raise the cap deliberately in config.json, or close the campaign.", 4)
    if cap is not None and spent > float(cap) * 0.8:
        print(f"run.py: campaign at ${spent:.4f} of ${float(cap):.2f} ({spent/float(cap)*100:.0f}%)", file=sys.stderr)

    # Durable start record: written before the model is launched, so a crash, a kill -9, or a lost probe
    # still leaves proof that this run happened. Finalised on every exit path below.
    start_rec = spend_dir / "runs" / f"{ts}-{role}-{unit}.run.json"
    start_rec.write_text(json.dumps({"ts": ts, "role": role, "unit": unit, "harness": harness,
                                     "model": model or "", "campaign": campaign, "cwd": str(cwd),
                                     "status": "started", "log": f"runs/{log.name}"}, indent=2) + "\n")

    wd = dict({"enabled": True, "poll_seconds": 10, "min_seconds": 45, "repeat_threshold": 8},
              **(cfg.get("loop_watchdog") or {}))
    start = time.time()
    loop_killed = None
    with open(log, "wb") as lf, open(os.devnull, "rb") as devnull:
        lf.write(f"# kit run {ts} role={role} unit={unit} harness={harness} model={model or '-'} cwd={cwd}\n".encode())
        lf.flush()
        # start_new_session puts the adapter and everything it spawns in their own process group, so a
        # timeout or watchdog kill reaches the model CLI too. Killing only the wrapper left the real
        # process running and billing.
        proc = subprocess.Popen([str(adapter), *prompt], cwd=cwd, stdin=devnull, stdout=lf,
                                stderr=subprocess.STDOUT, env=env, start_new_session=True)
        deadline = start + limit
        poll = max(2, int(wd.get("poll_seconds", 10)))
        rc_exit = None
        while rc_exit is None:
            try:
                rc_exit = proc.wait(timeout=poll)
                break
            except subprocess.TimeoutExpired:
                pass
            now = time.time()
            if now > deadline:
                kill_tree(proc); rc_exit = 124
                lf.write(b"\nrun.py: killed at wall-clock limit\n"); lf.flush()
                break
            # Watchdog: a model that lost its instructions repeats one tool call until the clock runs
            # out. Killing at the eighth repeat saves the rest of the cap; the run is a failure either way.
            if wd.get("enabled") and now - start >= int(wd.get("min_seconds", 45)):
                try:
                    d = subprocess.run([sys.executable, str(HERE / "analyze_run.py"), str(log), "--json",
                                        "--repeat-threshold", str(wd.get("repeat_threshold", 8))],
                                       capture_output=True, text=True, timeout=20)
                    r = json.loads(d.stdout) if d.stdout.strip() else {}
                except Exception:
                    r = {}
                if r.get("loop_suspected"):
                    kill_tree(proc); rc_exit = 125
                    loop_killed = f"{r.get('top_repeat_count')}x {r.get('top_repeat')!r}"
                    lf.write(f"\nrun.py: killed by the loop watchdog after {int(now-start)}s — {loop_killed}\n".encode())
                    lf.flush()
                    break
    secs = int(time.time() - start)

    # A failure to MEASURE must never become a failure to RECORD. Unknown cost stays unknown.
    after = cost = None
    probe_error = None
    if probe:
        try:
            # Provider usage reporting lags, and the lag is not constant. A delta of exactly zero after a
            # run that actually produced output means "not reported yet", not "free" - recording it as
            # $0.00 is how a real $0.0139 run was once booked as free. Re-probe with backoff, then admit
            # the measurement failed rather than inventing a zero.
            waits = cfg.get("usage_probe_backoff") or [int(cfg.get("usage_lag_seconds", 12)), 20, 45]
            for n, w in enumerate(waits):
                time.sleep(int(w))
                after = openrouter_usage(key)
                cost = round(after - before, 4)
                if cost > 0 or rc_exit != 0: break
                if n < len(waits) - 1:
                    print(f"run.py: usage still reports no change after {sum(int(x) for x in waits[:n+1])}s; re-probing",
                          file=sys.stderr)
            if cost == 0 and rc_exit == 0:
                cost = None
                probe_error = "provider reported no usage change; cost UNMEASURED, not zero"
                print(f"run.py: {probe_error}", file=sys.stderr)
        except Exception as e:
            probe_error = str(e)[:200]
            print(f"run.py: usage probe failed after the run ({probe_error}); cost recorded as UNKNOWN", file=sys.stderr)
    elif probe_mode == "harness" and cost_file.is_file():
        try: cost = round(float(cost_file.read_text().strip() or 0), 4)
        except ValueError: cost = None
    if cost_file.exists(): cost_file.unlink()

    diag = {}
    try:
        d = subprocess.run([sys.executable, str(HERE / "analyze_run.py"), str(log), "--json"],
                           capture_output=True, text=True, timeout=30)
        if d.stdout.strip(): diag = json.loads(d.stdout)
    except Exception as e:
        print(f"run.py: log analysis skipped ({e})", file=sys.stderr)

    validated = None
    if opts["--validate"]:
        kind = opts["--validate"]
        target = opts["--artifact"] or opts["--out"]
        args = [sys.executable, str(HERE / "validate.py"), kind, target]
        if kind == "packet": args += ["--repo", str(cwd)]
        v = subprocess.run(args, capture_output=True, text=True)
        validated = v.returncode == 0
        with open(log, "ab") as lf: lf.write(f"\n# validate {kind}: exit {v.returncode}\n{v.stdout}{v.stderr}".encode())

    row = {"ts": ts, "role": role, "unit": unit, "harness": harness, "model": model or "", "seconds": secs,
           "exit": rc_exit, "cost_usd": cost if cost is not None else 0.0, "cost_known": cost is not None,
           "cost_source": probe_mode, "cumulative_usd": after,
           "validated": validated, "log": f"runs/{log.name}", "campaign": cfg.get("campaign", ""),
           "prompt_tokens_est": est, "loop_suspected": diag.get("loop_suspected"),
           "distinct_tools": diag.get("distinct_tools"), "loop_killed": bool(loop_killed),
           "probe_error": probe_error, "status": "finished",
           "session": os.environ.get("KIT_SESSION_ID")}
    anomalies = []
    if rc_exit == 0 and cost is None and probe_mode != "none" and not model.startswith(local_prefixes):
        anomalies.append("unmeasured cost on a paid model: the request may never have reached it")
    if rc_exit == 0 and validated is False:
        anomalies.append(f"artefact failed {opts['--validate']} validation")
    if diag.get("loop_suspected") or loop_killed:
        anomalies.append("tool-call loop detected")
    if rc_exit == 124:
        anomalies.append("wall clock killed the run")
    if cost is not None and cost > float(cfg.get("run_cap_usd", 0.25)):
        anomalies.append(f"cost ${cost:.4f} exceeded the ${cfg.get('run_cap_usd', 0.25)} per-run cap")
    row["anomalies"] = anomalies
    for a in anomalies:
        # Anomalies are recorded and printed. They never block a later run: a formatting warning on
        # one receipt must not stop the next unit (measured 2026-09-11: three runs lost to that gate).
        print(f"run.py: NOTE {a}", file=sys.stderr)
    with open(spend_dir / "spend.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    # The brake. Caps answer "over the line?"; this answers "unlike every run before it?" and can
    # stop the campaign with nobody watching.
    kit_home.record(row, repo=Path(cwd), campaign=spend_dir)
    from kit.watchdog import check_and_record
    check_and_record(spend_dir, row, _s, say=lambda m: print(m, file=sys.stderr))
    cost_cell = f"${cost:.4f}" if cost is not None else "unknown"
    with open(spend_dir / "spend.md", "a") as f:
        f.write(f"| {ts} | {role} | {unit} | {secs}s | exit {rc_exit} | {cost_cell} | {after if after is not None else 'n/a'} | {row['log']} |\n")
    try:
        start_rec.write_text(json.dumps(row, indent=2) + "\n")
    except Exception:
        pass
    print(f"run: {role}/{unit} harness={harness} model={model or '-'} exit={rc_exit} time={secs}s cost={cost_cell} "
          f"cumulative={after} validated={validated} log={log}")
    if cost is None and rc_exit == 0 and model and not model.startswith(("lmstudio/", "ollama/")):
        print(f"run.py: WARNING — a successful run on a paid model reported no measurable cost. Either the usage "
              f"probe lagged or the request never reached {model}. Do not trust this run's output until the cost "
              f"appears in the ledger.", file=sys.stderr)
    if loop_killed:
        print(f"run.py: WATCHDOG KILL after {secs}s — {loop_killed}. The wall clock was not spent. "
              f"Treat as a failed run; change the prompt or the model before any re-run.", file=sys.stderr)
    if diag.get("loop_suspected") and not loop_killed:
        print(f"run.py: LOOP SUSPECTED — {diag['top_repeat_count']}x {diag['top_repeat']!r} across only "
              f"{diag['distinct_tools']} distinct tool call(s). The model most likely lost its instructions to "
              f"context truncation (~{est} prompt tokens). Shrink the prompt or use a larger-window model; "
              f"do NOT re-run unchanged.", file=sys.stderr)
    for m in diag.get("truncation_markers") or []:
        print(f"run.py: TRUNCATION MARKER {m!r} in the log", file=sys.stderr)

    # Post-run guards. These are overrun REPORTS, not spend prevention: the money is already committed by
    # the time they fire. Prevention is the pre-launch admission check above.
    if cost is not None and cost > float(cfg.get("run_cap_usd", 0.25)):
        die(f"OVERRUN: this run cost ${cost:.4f}, over the ${cfg['run_cap_usd']} per-run cap. Already spent; "
            f"the next run is what this stops.", 3)
    spent_after = campaign_spent(spend_dir, campaign)[0]
    if cap is not None and spent_after > float(cap):
        die(f"OVERRUN: campaign {campaign!r} is now at ${spent_after:.4f}, over its ${float(cap):.2f} cap. "
            f"No further run will be admitted until the cap is changed deliberately.", 4)
    if validated is False:
        die(f"artefact failed validation ({opts['--validate']}); see log", 5)
    if anomalies and rc_exit == 0:
        # The harness said success. The evidence says otherwise. A non-zero exit here is what stops an
        # orchestrator — human or model — from reading exit=0 and moving on.
        die("ANOMALY: " + "; ".join(anomalies) + f". Run record: {start_rec}. This run is NOT a success. "
            f"Read the log, fix the cause, and acknowledge with `kit do --acknowledge {ts}` only if you have "
            f"verified the output by hand.", 13)
    sys.exit(rc_exit)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
