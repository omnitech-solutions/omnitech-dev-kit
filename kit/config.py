#!/usr/bin/env python3
"""config.py — `kit.yaml` / `kit.json`: layered settings with restricted, explainable rules.

## Why rules and not logic

This config decides how much a model may spend and what it may touch. It is the guard. So it is
data, never code: no `kit.config.js`, no `eval`, no expression language that can reach the
filesystem or the network. The prior art that ages well is match-then-apply — ESLint `overrides`,
Prettier `overrides`, Renovate `packageRules`, GitHub Actions' deliberately restricted `if:`,
CEL in Kubernetes admission. The prior art that does not is executable config, which cannot be
diffed meaningfully, cannot be validated without running it, and cannot answer "why is this value
what it is?".

Every resolved value here can be explained:

    kit config explain caps.run_usd
    caps.run_usd = 0.10
      default        0.25
      campaign       0.25
      rules[1]       0.10    when role=implementer, repo=legion-os-surveys   <- winner

## Shape

    caps:   {run_usd: 0.25, unit_usd: 0.50, session_usd: 2.00, campaign_usd: 5.00}
    output: {heartbeat_seconds: 30, console: true, quiet: false}

    rules:
      - when: {role: verifier}
        set:  {output: {heartbeat_seconds: 60}}
      - when: {repo: {glob: "legion-*"}, role: implementer}
        set:  {caps: {run_usd: 0.10}}
      - when: {diff_lines: {gt: 300}}
        set:  {gates: {scope: full}}

Rules are evaluated in order; later matches win. A rule with no `when` always matches. Facts you
may match on are fixed (see FACTS) — matching on anything else is an error at load time, not a
silent no-match, because a typo'd predicate that quietly never fires is how a guard stops guarding.
Deliberately absent: time-of-day and random facts. Config that behaves differently at 2am is a
debugging nightmare.
"""
import fnmatch, json, os
from pathlib import Path

FACTS = {"role", "harness", "repo", "campaign", "unit", "model", "session",
         "diff_lines", "changed_files", "scope"}
OPS = {"eq", "ne", "in", "not_in", "glob", "gt", "gte", "lt", "lte", "exists"}
NAMES = ("kit.yaml", "kit.yml", "kit.json")


class ConfigError(Exception):
    """Raised for anything malformed. The kit refuses rather than guessing."""


# --------------------------------------------------------------------------------------- parsing
def _parse_yaml(text: str, where: str):
    """YAML via PyYAML, or a clear refusal. Deliberately not hand-rolled.

    This file parses spending caps and permission scopes. A hand-written YAML subset that
    mis-reads one of them fails silently and expensively — three real bugs surfaced in ten
    minutes of writing one, which is the argument against it. JSON is the zero-dependency
    path; YAML is the comfortable one and costs a dependency that is trivial to satisfy.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ConfigError(
            f"{where}: reading YAML needs PyYAML, which is not importable here.\n"
            f"  fix:  pip install pyyaml    (or run the kit under `uv run --with pyyaml`)\n"
            f"  or:   use kit.json — JSON needs nothing and supports exactly the same shape.\n"
            f"  The kit refuses to guess at YAML rather than risk mis-reading a cap.")
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{where}: {e}")


def find(directory: Path):
    """The one config in this directory. Two is an error: a silent winner is a footgun."""
    found = [directory / n for n in NAMES if (directory / n).is_file()]
    if len(found) > 1:
        raise ConfigError(f"{directory} has {len(found)} config files ({', '.join(f.name for f in found)}). "
                          f"Keep one — the kit will not pick a winner for you.")
    return found[0] if found else None


def read(path: Path) -> dict:
    text = path.read_text()
    doc = json.loads(text) if path.suffix == ".json" else _parse_yaml(text, str(path))
    if not isinstance(doc, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    validate(doc, str(path))
    return doc


# ------------------------------------------------------------------------------------ validation
def validate(doc: dict, where: str):
    for i, rule in enumerate(doc.get("rules") or []):
        if not isinstance(rule, dict) or "set" not in rule:
            raise ConfigError(f"{where}: rules[{i}] needs a `set` block")
        for fact, pred in (rule.get("when") or {}).items():
            if fact not in FACTS:
                raise ConfigError(f"{where}: rules[{i}] matches on unknown fact {fact!r}. "
                                  f"Known facts: {', '.join(sorted(FACTS))}. A predicate that can never "
                                  f"fire is how a guard stops guarding, so this is an error.")
            if isinstance(pred, dict):
                for op in pred:
                    if op not in OPS:
                        raise ConfigError(f"{where}: rules[{i}].when.{fact} uses unknown operator "
                                          f"{op!r}. Known: {', '.join(sorted(OPS))}.")


# ------------------------------------------------------------------------------------- matching
def _test(value, pred) -> bool:
    if not isinstance(pred, dict):
        return value == pred
    for op, want in pred.items():
        if op == "eq" and value != want: return False
        if op == "ne" and value == want: return False
        if op == "in" and value not in want: return False
        if op == "not_in" and value in want: return False
        if op == "glob" and not (isinstance(value, str) and fnmatch.fnmatch(value, want)): return False
        if op == "exists" and (value is not None) != bool(want): return False
        if op in ("gt", "gte", "lt", "lte"):
            if value is None:
                return False
            try:
                v, w = float(value), float(want)
            except (TypeError, ValueError):
                return False
            if op == "gt" and not v > w: return False
            if op == "gte" and not v >= w: return False
            if op == "lt" and not v < w: return False
            if op == "lte" and not v <= w: return False
    return True


def matches(rule: dict, facts: dict) -> bool:
    return all(_test(facts.get(f), p) for f, p in (rule.get("when") or {}).items())


def describe(rule: dict) -> str:
    when = rule.get("when") or {}
    if not when:
        return "always"
    return ", ".join(f"{k}={v if not isinstance(v, dict) else next(iter(v.items()))}" for k, v in when.items())


def _merge(base: dict, over: dict) -> dict:
    """Local copy: config.py must not import settings, or the two cannot be loaded independently."""
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def apply_rules(settings: dict, doc: dict, facts: dict, provenance: dict, label: str):
    """Later matches win. Every applied value is attributed to its rule index and reason."""
    for i, rule in enumerate(doc.get("rules") or []):
        if not matches(rule, facts):
            continue
        settings = _merge(settings, rule.get("set") or {})
        for section, values in (rule.get("set") or {}).items():
            if isinstance(values, dict):
                for k in values:
                    provenance[f"{section}.{k}"] = f"{label} rules[{i}] ({describe(rule)})"
    return settings
