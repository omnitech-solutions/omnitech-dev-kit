"""Layered settings: everything tunable, nothing tuned by accident.

Precedence is default < machine < campaign < session(env) < flags, and the layer that set a value
is reported so a surprising number always has a visible cause.
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from kit.settings import DEFAULTS, load, output_for  # noqa: E402


def campaign(**cfg):
    d = Path(tempfile.mkdtemp())
    (d / "config.json").write_text(json.dumps(cfg))
    return d


def test_defaults_are_sane():
    s, _ = load()
    assert s["output"]["heartbeat_seconds"] == 30
    assert s["caps"]["run_usd"] == 0.25 and s["caps"]["session_usd"] == 2.00


def test_campaign_overrides_default_and_is_attributed():
    s, prov = load(campaign(output={"heartbeat_seconds": 5}))
    assert s["output"]["heartbeat_seconds"] == 5
    assert prov["output.heartbeat_seconds"] == "campaign"


def test_env_session_layer_beats_campaign():
    c = campaign(output={"heartbeat_seconds": 5}, caps={"session_usd": 9})
    os.environ["KIT_HEARTBEAT"] = "45"
    os.environ["KIT_CAP_SESSION"] = "0.5"
    try:
        s, prov = load(c)
        assert s["output"]["heartbeat_seconds"] == 45
        assert s["caps"]["session_usd"] == 0.5
        assert prov["output.heartbeat_seconds"] == "session"
    finally:
        del os.environ["KIT_HEARTBEAT"], os.environ["KIT_CAP_SESSION"]


def test_flags_beat_everything():
    s, prov = load(campaign(output={"heartbeat_seconds": 5}), flags={"output": {"heartbeat_seconds": 1}})
    assert s["output"]["heartbeat_seconds"] == 1 and prov["output.heartbeat_seconds"] == "flags"


def test_legacy_flat_caps_still_honoured():
    s, _ = load(campaign(run_cap_usd=0.05, campaign_cap_usd=1.0))
    assert s["caps"]["run_usd"] == 0.05 and s["caps"]["campaign_usd"] == 1.0


def test_per_role_output_and_quiet():
    s, _ = load(campaign(output={"heartbeat_seconds": 30, "per_role": {"verifier": {"heartbeat_seconds": 90}}}))
    assert output_for(s, "verifier")["heartbeat_seconds"] == 90
    assert output_for(s, "implementer")["heartbeat_seconds"] == 30
    q, _ = load(campaign(output={"quiet": True}))
    assert output_for(q, "implementer")["heartbeat_seconds"] == 0


def _campaign_with_config():
    d = Path(tempfile.mkdtemp())
    (d / "AGENTS.md").write_text("law")
    cfg = json.loads((KIT / "templates" / "config.json").read_text())
    cfg["campaign_baseline_usd"] = 0
    (d / "config.json").write_text(json.dumps(cfg))
    return d


def _seed_machine_ledger(kit_home, session, cost, ts="20260912T000000"):
    """Spend lands in the machine ledger, which is what the session cap reads."""
    sessions = Path(kit_home) / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{session}.jsonl").write_text(json.dumps(
        {"ts": ts, "role": "implementer", "unit": "U", "cost_usd": cost,
         "cost_known": True, "session": session}) + "\n")


def _dry_run(d, env):
    return subprocess.run([sys.executable, str(KIT / "kit" / "run.py"), "reader", "T", str(d),
                           "--config", str(d / "config.json"), "--no-advice", "--dry-run",
                           "--", f"@{d / 'AGENTS.md'}", "q"],
                          capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", **env})


def test_session_cap_refuses_before_launching(isolated_kit_home):
    d = _campaign_with_config()
    _seed_machine_ledger(isolated_kit_home, "S1", 3.0)
    r = _dry_run(d, {"KIT_HOME": isolated_kit_home, "KIT_SESSION_ID": "S1", "KIT_CAP_SESSION": "2.0"})
    assert r.returncode == 4, (r.returncode, r.stderr[-300:])
    assert "session S1" in r.stderr and "Nothing was launched" in r.stderr


def test_session_cap_ignores_other_sessions(isolated_kit_home):
    d = _campaign_with_config()
    _seed_machine_ledger(isolated_kit_home, "OTHER", 3.0)
    r = _dry_run(d, {"KIT_HOME": isolated_kit_home, "KIT_SESSION_ID": "S2", "KIT_CAP_SESSION": "2.0"})
    assert r.returncode == 0, r.stderr[-300:]


def test_session_cap_binds_ACROSS_campaigns(isolated_kit_home):
    """The bug this layer exists for.

    spend.jsonl is per campaign, so two campaigns in one session each got their own budget and the
    session cap silently did not bind. Spend recorded while working campaign A must stop campaign B.
    """
    _seed_machine_ledger(isolated_kit_home, "S3", 3.0)      # earned in campaign A
    b = _campaign_with_config()                              # a different campaign, no local spend
    assert not (b / "spend.jsonl").exists()
    r = _dry_run(b, {"KIT_HOME": isolated_kit_home, "KIT_SESSION_ID": "S3", "KIT_CAP_SESSION": "2.0"})
    assert r.returncode == 4, (r.returncode, r.stderr[-300:])
    assert "session S3" in r.stderr


def test_daily_cap_spans_sessions(isolated_kit_home):
    import time as _t
    today = _t.strftime("%Y%m%d")
    _seed_machine_ledger(isolated_kit_home, "morning", 1.5, ts=f"{today}T090000")
    d = _campaign_with_config()
    r = _dry_run(d, {"KIT_HOME": isolated_kit_home, "KIT_SESSION_ID": "afternoon", "KIT_CAP_DAILY": "1.0"})
    assert r.returncode == 4 and "today" in r.stderr


def test_machine_halt_stops_every_campaign(isolated_kit_home):
    (Path(isolated_kit_home) / "HALTED.json").write_text(json.dumps(
        {"at": "now", "reasons": ["a runaway unit in another campaign"]}))
    d = _campaign_with_config()
    r = _dry_run(d, {"KIT_HOME": isolated_kit_home})
    assert r.returncode == 4 and "Every campaign on this machine" in r.stderr
