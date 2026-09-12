#!/usr/bin/env python3
"""Admission refusals in run.py. Stdlib only: python3 tests/test_run_admission.py

These exist because of one afternoon: a planner role with no model fell through to the harness default,
which was a local 8K-context model, and a 489-second run reported exit=0 with no cost. Every assertion
here is a way that run must now fail loudly instead. No model is called; every case stops before launch.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
RUN = KIT / "kit" / "run.py"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name).resolve()
        (self.d / "AGENTS.md").write_text("# law\n")
        cfg = json.loads((KIT / "templates" / "config.json").read_text())
        cfg["campaign_baseline_usd"] = 0
        self.cfg = self.d / "config.json"
        self.cfg.write_text(json.dumps(cfg))

    def tearDown(self):
        self.tmp.cleanup()

    def run_py(self, *args, cfg=None, env=None):
        return subprocess.run([sys.executable, str(RUN), "reader", "T", str(self.d), "--config", str(cfg or self.cfg),
                               "--no-advice", *args, "--", f"@{self.d / 'AGENTS.md'}", "q"],
                              capture_output=True, text=True, timeout=60,
                              env={"PATH": "/usr/bin:/bin", **(env or {})})

    def set_cfg(self, **changes):
        c = json.loads(self.cfg.read_text()); c.update(changes); self.cfg.write_text(json.dumps(c))


class TestModelAdmission(Base):
    def test_local_model_is_refused_unless_opted_in(self):
        p = self.run_py("--model", "lmstudio/qwen/qwen3-coder-30b", "--dry-run")
        self.assertEqual(p.returncode, 11, p.stderr)
        self.assertIn("allow_local_models", p.stderr)

    def test_local_model_allowed_with_explicit_opt_in(self):
        self.set_cfg(allow_local_models=True)
        p = self.run_py("--model", "lmstudio/qwen/qwen3-coder-30b", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_unknown_provider_prefix_is_refused(self):
        p = self.run_py("--model", "mystery/model", "--dry-run")
        self.assertEqual(p.returncode, 11)
        self.assertIn("allowed_model_prefixes", p.stderr)

    def test_role_with_no_model_is_refused_not_defaulted(self):
        c = json.loads(self.cfg.read_text()); c.pop("models", None)
        for r in c["roles"].values(): r.pop("model", None)
        self.cfg.write_text(json.dumps(c))
        # not a dry run: the refusal must fire on the real path, before any harness is touched
        p = self.run_py()
        self.assertEqual(p.returncode, 11, p.stderr)
        self.assertIn("harness would silently use its own default", p.stderr)

    def test_allowed_model_dry_run_proceeds(self):
        p = self.run_py("--model", "openrouter/z-ai/glm-5.3-flash", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("dry-run:", p.stdout)


ANOMALY = "unmeasured cost on a paid model: the request may never have reached it"


class TestLaggedCostReconcile(Base):
    def write_spend(self, cumulative):
        row = {"ts": "20260911T000000", "role": "reader", "unit": "T", "harness": "omp", "model": "openrouter/x",
               "exit": 0, "cost_usd": 0.0, "cost_known": False, "cost_source": "openrouter",
               "cumulative_usd": cumulative, "probe_error": "provider reported no usage change",
               "anomalies": [ANOMALY], "status": "finished"}
        (self.d / "spend.jsonl").write_text(json.dumps(row) + "\n")

    def probe_with(self, value):
        probe = self.d / "probe.txt"
        probe.write_text(str(value))
        return self.run_py("--dry-run", env={"KIT_USAGE_PROBE_FILE": str(probe)})

    def test_lagged_cost_is_reconciled_from_next_probe(self):
        self.write_spend(3.604)
        p = self.probe_with(3.778)
        self.assertEqual(p.returncode, 0, p.stderr)
        row = json.loads((self.d / "spend.jsonl").read_text().splitlines()[0])
        self.assertEqual(row["cost_usd"], 0.174)
        self.assertTrue(row["cost_known"])
        self.assertTrue(row["reconciled"])
        self.assertEqual(row["anomalies"], [])
        self.assertIn("reconciled lagged cost $0.1740 for reader/T", p.stderr)

    def test_no_reconcile_without_delta(self):
        self.write_spend(3.604)
        p = self.probe_with(3.604)
        self.assertEqual(p.returncode, 0, p.stderr)
        row = json.loads((self.d / "spend.jsonl").read_text().splitlines()[0])
        self.assertFalse(row["cost_known"])
        self.assertEqual(row["cost_usd"], 0.0)
        self.assertNotIn("reconciled", row)
        self.assertEqual(row["anomalies"], [ANOMALY])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("dry-run:", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
