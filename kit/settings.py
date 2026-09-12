#!/usr/bin/env python3
"""settings.py — layered settings. Everything tunable is tunable, and nothing is tuned by accident.

Precedence, lowest to highest:

    1. kit defaults (below)
    2. machine     ~/.config/omnitech-dev-kit/config.json   — your standing preferences
    3. campaign    <campaign>/config.json                   — this piece of work
    4. session     $KIT_* environment variables             — this shell / this background task
    5. flags       --heartbeat 60, --quiet, --log FILE       — this one invocation

A setting resolved from a layer above the campaign is reported, so a surprising value always has a
visible cause. Nothing here changes what a worker may do — that stays in run.py's admission.
"""
import json, os
from pathlib import Path

MACHINE = Path(os.environ.get("KIT_CONFIG_HOME", "~/.config/omnitech-dev-kit")).expanduser() / "config.json"

DEFAULTS = {
    # --- output: how a run reports itself -------------------------------------------------
    "output": {
        "heartbeat_seconds": 30,     # 0 disables. A stage that prints nothing looks hung.
        "console": True,             # stream stage output to stdout
        "log": None,                 # extra copy to this path; null = the campaign's runs/ only
        "quiet": False,              # suppress heartbeats and per-stage chatter, keep verdicts
        "per_role": {},              # {"verifier": {"heartbeat_seconds": 60}}
    },
    # --- money: every cap that can stop a run ---------------------------------------------
    "caps": {
        "run_usd": 0.25,             # one model call            (run.py, exit 3 / projected exit 10)
        "unit_usd": 0.50,            # one ledger row, all stages (exit 3)
        "session_usd": 2.00,         # one KIT_SESSION_ID         (exit 4)
        "campaign_usd": 5.00,        # the whole campaign         (exit 4)
        "daily_usd": None,           # null = off
    },
    # --- targets: reported, never enforced -------------------------------------------------
    "targets": {"unit_usd": 0.15, "unit_minutes": 15},
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _from_env() -> dict:
    """KIT_HEARTBEAT, KIT_QUIET, KIT_LOG, KIT_CONSOLE, KIT_CAP_RUN/UNIT/SESSION/CAMPAIGN/DAILY."""
    e, out = os.environ, {}
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    o, c = {}, {}
    if e.get("KIT_HEARTBEAT") is not None and num(e["KIT_HEARTBEAT"]) is not None:
        o["heartbeat_seconds"] = int(num(e["KIT_HEARTBEAT"]))
    if e.get("KIT_QUIET"):
        o["quiet"] = e["KIT_QUIET"] not in ("0", "false", "")
    if e.get("KIT_CONSOLE"):
        o["console"] = e["KIT_CONSOLE"] not in ("0", "false", "")
    if e.get("KIT_LOG"):
        o["log"] = e["KIT_LOG"]
    for key, env in (("run_usd", "KIT_CAP_RUN"), ("unit_usd", "KIT_CAP_UNIT"),
                     ("session_usd", "KIT_CAP_SESSION"), ("campaign_usd", "KIT_CAP_CAMPAIGN"),
                     ("daily_usd", "KIT_CAP_DAILY")):
        if e.get(env) is not None and num(e[env]) is not None:
            c[key] = num(e[env])
    if o:
        out["output"] = o
    if c:
        out["caps"] = c
    return out


def load(campaign: Path = None, flags: dict = None, facts: dict = None):
    """Returns (settings, provenance) where provenance maps a dotted key to the layer that set it.

    `facts` (role, repo, unit, diff_lines, …) drive the `rules:` block of any kit.yaml / kit.json
    on the way through; see kit/config.py for why rules are matchers and not code.
    """
    from . import config as C
    docs = []            # (label, doc) in precedence order, for rule evaluation after merging
    layers = [("default", DEFAULTS)]
    for label, directory in (("machine", MACHINE.parent), ("repo", Path.cwd())):
        try:
            f = C.find(directory)
        except C.ConfigError as e:
            raise SystemExit(f"kit: {e}")
        if f:
            doc = C.read(f)
            layers.append((label, doc))
            docs.append((label, doc))
    if MACHINE.is_file():
        try:
            layers.append(("machine", json.loads(MACHINE.read_text())))
        except ValueError:
            pass
    if campaign:
        try:
            f = C.find(campaign)
        except C.ConfigError as e:
            raise SystemExit(f"kit: {e}")
        if f:
            doc = C.read(f)
            layers.append(("campaign", doc))
            docs.append(("campaign", doc))
    if campaign and (campaign / "config.json").is_file():
        try:
            raw = json.loads((campaign / "config.json").read_text())
            # campaign configs may still carry the flat legacy keys; fold them in
            legacy = {"caps": {k: raw[j] for k, j in
                               (("run_usd", "run_cap_usd"), ("campaign_usd", "campaign_cap_usd")) if j in raw}}
            layers.append(("campaign", _merge({k: v for k, v in raw.items()
                                               if k in ("output", "caps", "targets")}, legacy)))
        except ValueError:
            pass
    layers.append(("session", _from_env()))
    if flags:
        layers.append(("flags", flags))

    settings, provenance = dict(DEFAULTS), {}
    for name, layer in layers[1:]:
        for section, values in (layer or {}).items():
            if not isinstance(values, dict):
                continue
            for k, v in values.items():
                provenance[f"{section}.{k}"] = name
        settings = _merge(settings, layer)
    for label, doc in docs:                       # rules last: they are the most specific statement
        settings = C.apply_rules(settings, doc, facts or {}, provenance, label)
    return settings, provenance


def output_for(settings: dict, role: str) -> dict:
    """Per-role output settings: `output.per_role.<role>` wins over `output`."""
    o = dict(settings.get("output") or {})
    o = _merge(o, (o.get("per_role") or {}).get(role, {}))
    if o.get("quiet"):
        o["heartbeat_seconds"] = 0
    return o
