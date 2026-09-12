#!/usr/bin/env python3
"""init_campaign.py — scaffold a campaign: config, AGENTS.md, gates, ledger, folders. No model, no network."""
import json, subprocess, sys, time
from pathlib import Path

from . import ledger
from .campaign import DEFAULT_MODELS, constraints_text, ensure_gates, die, repo_root, say, slug

AGENTS = """# {slug} — the standing context for every run in this campaign

**Oracle (reference):** {oracle}
**Subject (ours):** {subject}

## The boundary
A worker may edit only the files listed in its packet's §2. Everything else is protected, including
every test not named in §5. A worker that needs a file outside §2 stops and says so.

## Invariants (not advisory)
- No new dependencies without the packet saying so.
- No edits to generated or vendored files.
- The oracle is **observe-only**: no sends, publishes, saves, deletes or account changes, ever.
- Tests assert against the real artefact — no mocks of the thing under test, no `assert True`.
- Never commit, stash, reset, or touch the primary checkout. You are in a worktree.
- Never read or print environment values.

## Gates (fail-closed, with counts)
{gates}

## What "done" means
A worker's ACCEPT is a claim. The unit is done when the orchestrator has read the diff against §2,
read the test, mutation-tested it, confirmed the behaviour live, and written `receipts/<id>-live.md`.
"""


def cmd_init(slug_arg: str, oracle: str, subject: str, harness: str):
    repo = repo_root() or die("not inside a git repository")
    name = slug(slug_arg, 40)
    campaign = repo / ".kit" / name
    if (campaign / "config.json").is_file():
        say(f"campaign already exists: {campaign.relative_to(repo)}")
        return 0
    for sub in ("packets", "receipts", "runs", "fixtures/oracle", "fixtures/subject"):
        (campaign / sub).mkdir(parents=True, exist_ok=True)

    example = next((c for c in (Path(__file__).resolve().parent.parent / "templates" / "config.json",) if c.is_file()), None)
    cfg = json.loads(example.read_text()) if example else {}
    cfg.update({"harness": harness, "campaign": f"{repo.name}/{name}", "campaign_baseline_usd": None,
                "oracle": oracle, "subject": subject, "default_files": "",
                "models": dict(DEFAULT_MODELS.get(harness, DEFAULT_MODELS["omp"])),
                "unit_targets": {"usd": 0.15, "minutes": 15},
                "live_gate": True, "crux": {"enabled": True}})
    cfg.pop("allow_capability_gap", None) or cfg.setdefault("allow_capability_gap", {})
    (campaign / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")

    say(f"kit init: {campaign.relative_to(repo)}")
    say("  detecting gates from the repository (no baselines measured — run `kit gates --detect --measure` for those)")
    gates_doc = ensure_gates(campaign, repo, measure=False)
    n = len([g for g in gates_doc.get("gates", []) if g.get("kind") != "live"])
    (campaign / "AGENTS.md").write_text(AGENTS.format(slug=name, oracle=oracle or "<not set>",
                                                      subject=subject or "<not set>",
                                                      gates=constraints_text(gates_doc, repo)))
    ledger.path(campaign).write_text(ledger.template(name, oracle or "<not set>", subject or "<not set>"))
    say(f"  gates {n} enforced + a live gate that only you can close")
    say(f"  config   {(campaign / 'config.json').relative_to(repo)}   (models named per role; no default is inherited)")
    say(f"  context  {(campaign / 'AGENTS.md').relative_to(repo)}   ← edit the invariants for this project")
    say(f"  ledger   {ledger.path(campaign).relative_to(repo)}")
    say('\nNext:\n  kit ledger add "<one observable behaviour>"\n  kit next')
    return 0
