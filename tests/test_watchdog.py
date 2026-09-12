"""The brake. It must fire on the runs that actually got away from us, and stay quiet on normal ones.

Numbers are the real ones from 2026-09-11/12: normal implementer runs were $0.020–$0.032 over
172–249s; the vague-packet run was $1.03 over 720s and sat comfortably inside every cap. That is
the case caps cannot catch and this module exists for.
"""
import json
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from kit.watchdog import check_and_record, evaluate, halted, settings_for  # noqa: E402

W = settings_for({"caps": {"unit_usd": 0.50}})


def row(role="implementer", unit="U", cost=0.02, secs=180, exit_=0):
    return {"role": role, "unit": unit, "cost_usd": cost, "seconds": secs, "exit": exit_,
            "cost_known": True, "ts": "20260912T000000"}


def normal(n=4, unit="U"):
    return [row(unit=unit, cost=c, secs=s) for c, s in
            [(0.020, 172), (0.032, 249), (0.024, 190), (0.028, 210)][:n]]


def test_normal_run_is_silent():
    assert evaluate(normal() + [row()], row(), W) == []


def test_the_1_03_run_halts_even_though_every_cap_allowed_it():
    bad = row(cost=1.03, secs=720)
    findings = evaluate(normal() + [bad], bad, W)
    assert "HALT" in [s for s, _ in findings]
    assert any("x the median" in m for _, m in findings)


def test_no_baseline_means_no_deviation_halt():
    """Two samples is not a baseline. Absolutes still apply; guesses do not."""
    bad = row(cost=1.03, secs=720)
    assert not any("median" in m for _, m in evaluate(normal(2) + [bad], bad, W))


def test_unit_budget_across_stages_halts():
    rows = [row(cost=0.30), row(role="verifier", cost=0.25)]
    assert any(s == "HALT" and "budget" in m for s, m in evaluate(rows, rows[-1], W))


def test_three_consecutive_failures_halt():
    rows = [row(exit_=1), row(exit_=1), row(exit_=1)]
    assert any(s == "HALT" and "not converging" in m for s, m in evaluate(rows, rows[-1], W))


def test_slow_but_cheap_only_warns():
    """Time deviation is a warning: a slow cheap run is worth knowing about, not worth stopping."""
    slow = row(cost=0.03, secs=2000)
    sev = {s for s, _ in evaluate(normal() + [slow], slow, W)}
    assert sev == {"WARN"}


def test_halt_is_written_and_survives_the_process():
    """A dead-man's switch: it needs nobody present, and it outlives the run that tripped it."""
    d = Path(tempfile.mkdtemp())
    bad = row(cost=1.03, secs=720)
    (d / "spend.jsonl").write_text("\n".join(json.dumps(r) for r in normal() + [bad]) + "\n")
    check_and_record(d, bad, {"caps": {"unit_usd": 0.50}}, say=lambda m: None)
    h = halted(d)
    assert h and h["reasons"] and h["unit"] == "U"
    assert (d / "HALTED.json").is_file()


def test_disabled_watchdog_says_nothing():
    bad = row(cost=1.03, secs=720)
    assert evaluate(normal() + [bad], bad, settings_for({"watchdog": {"enabled": False}})) == []
