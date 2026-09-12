#!/usr/bin/env python3
"""Self-test for the trusted gate runner. Stdlib only: python3 tests/test_gate_runner.py

The gate runner decides what "verified" means, so these assertions are the ones that matter most:
a narrow run must never masquerade as full coverage, a suite the change cannot touch must not read as
red, a gate that was already failing must not be blamed on this candidate, and a real regression must
still fail. No model is called.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
RUNNER = KIT / "kit" / "gates.py"


def run(args, cwd):
    return subprocess.run([sys.executable, str(RUNNER), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", "."], cwd=self.wt, check=True)
        (self.wt / "src.txt").write_text("base\n")
        subprocess.run(["git", "add", "-A"], cwd=self.wt, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                       cwd=self.wt, check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def gates(self, rows):
        f = self.wt / "gates.json"
        f.write_text(json.dumps({"gates": rows}))
        return f

    def gate(self, name="unit", command="true", kind="unit", rank=3, baseline=None, script=""):
        return {"gate": name, "kind": kind, "rank": rank, "dir": ".", "command": command,
                "script": script, "baseline": baseline or {"exit": 0, "token": "clean"}}

    def record(self, args):
        out = self.wt / "rec.json"
        p = run([str(self.wt), "--gates", str(self.gates_file), "--out", str(out), *args], self.wt)
        return json.loads(out.read_text()), p


class TestScopeIntegrity(Base):
    def test_a_selected_run_is_never_acceptance_eligible(self):
        self.gates_file = self.gates([self.gate(command="true")])
        doc, _ = self.record(["--scope", "selected"])
        self.assertEqual(doc["scope"], "selected")
        self.assertFalse(doc["acceptance_eligible"],
                         "a narrow run must not be able to support an ACCEPT")

    def test_a_clean_full_run_is_acceptance_eligible(self):
        self.gates_file = self.gates([self.gate(command="true")])
        doc, _ = self.record(["--scope", "full"])
        self.assertTrue(doc["acceptance_eligible"])

    def test_receipt_line_marks_a_selected_run_as_not_a_full_bar_claim(self):
        (self.wt / "a.test.js").write_text("x")
        self.gates_file = self.gates([self.gate(command="echo 3 passed", script="vitest run")])
        p = run([str(self.wt), "--gates", str(self.gates_file), "--scope", "selected", "--receipt-lines"], self.wt)
        self.assertIn("SELECTED", p.stdout, "a narrowed gate line must say so in the receipt")


class TestLiveGates(Base):
    def test_live_gates_are_not_run_by_default(self):
        # Assert on a side effect, not on the report text: the command name appears in the report by
        # design, so matching stdout would pass even if the gate had executed.
        canary = self.wt / "live-ran.canary"
        self.gates_file = self.gates([self.gate(name="e2e", kind="live", rank=5,
                                                command=f"touch {canary}")])
        doc, _ = self.record(["--scope", "full"])
        self.assertEqual(doc["ran"], 0)
        self.assertTrue(doc["live_not_run"])
        self.assertFalse(canary.exists(), "a live gate must not execute without --include-live")

    def test_live_gates_run_only_when_explicitly_included(self):
        self.gates_file = self.gates([self.gate(name="e2e", kind="live", rank=5, command="true")])
        doc, _ = self.record(["--scope", "full", "--include-live"])
        self.assertEqual(doc["ran"], 1)


class TestClassification(Base):
    def test_a_real_regression_fails(self):
        self.gates_file = self.gates([self.gate(command="exit 1")])
        doc, p = self.record(["--scope", "full"])
        self.assertEqual(doc["failed"], 1)
        self.assertFalse(doc["acceptance_eligible"])
        self.assertEqual(p.returncode, 1)

    def test_a_pre_existing_failure_is_not_blamed_on_this_candidate(self):
        g = self.gate(command="echo 677 passed; exit 1",
                      baseline={"exit": 1, "token": "670 passed"})
        self.gates_file = self.gates([g])
        doc, _ = self.record(["--scope", "full"])
        self.assertEqual(doc["results"][0]["status"], "no_regression")
        self.assertEqual(doc["failed"], 0)
        self.assertTrue(doc["acceptance_eligible"])

    def test_a_dropped_passing_count_is_a_regression_even_on_exit_zero(self):
        g = self.gate(command="echo 660 passed", baseline={"exit": 0, "token": "670 passed"})
        self.gates_file = self.gates([g])
        doc, _ = self.record(["--scope", "full"])
        self.assertEqual(doc["results"][0]["status"], "regression")
        self.assertFalse(doc["acceptance_eligible"])

    def test_no_matching_tests_reads_as_not_applicable_not_red(self):
        (self.wt / "a.test.js").write_text("x")
        g = self.gate(command="echo 'No test files found'; exit 1", script="vitest run")
        self.gates_file = self.gates([g])
        doc, _ = self.record(["--scope", "selected"])
        self.assertEqual(doc["results"][0]["status"], "not_applicable")
        self.assertEqual(doc["failed"], 0)


class TestDedupe(Base):
    def test_dedupe_keeps_distinct_suites_and_drops_only_a_true_duplicate(self):
        self.gates_file = self.gates([
            self.gate(name="rail", command="echo 58 passed", baseline={"exit": 0, "token": "58 passed"}),
            self.gate(name="unit", command="echo 670 passed; exit 1", baseline={"exit": 1, "token": "670 passed"}),
            self.gate(name="unit", command="echo 670 passed", baseline={"exit": 0, "token": "670 passed"}),
        ])
        doc, _ = self.record(["--scope", "full"])
        ran = [r["gate"] for r in doc["results"]]
        self.assertEqual(sorted(ran), ["rail", "unit"], "rail must run; exactly one unit gate must run")
        self.assertEqual(len(doc["superseded"]), 1)
        self.assertIn("exit 1", doc["superseded"][0])


    def test_selected_scope_never_compares_counts_to_the_full_baseline(self):
        (self.wt / "a.test.js").write_text("x")
        g = self.gate(command="echo 7 passed", script="vitest run", baseline={"exit": 0, "token": "674 passed"})
        self.gates_file = self.gates([g])
        doc, _ = self.record(["--scope", "selected"])
        self.assertEqual(doc["results"][0]["status"], "pass", doc["results"][0])


class TestCandidateBinding(Base):
    def test_digest_changes_when_the_candidate_changes(self):
        self.gates_file = self.gates([self.gate(command="true")])
        first, _ = self.record(["--scope", "full"])
        (self.wt / "src.txt").write_text("edited\n")
        second, _ = self.record(["--scope", "full"])
        self.assertNotEqual(first["candidate_digest"], second["candidate_digest"],
                            "a record must not be reusable for a candidate it did not examine")

    def test_changed_files_exclude_dependencies(self):
        (self.wt / "node_modules").mkdir()
        (self.wt / "node_modules" / "junk.js").write_text("x")
        (self.wt / "real.ts").write_text("x")
        self.gates_file = self.gates([self.gate(command="true")])
        doc, _ = self.record(["--scope", "full"])
        self.assertIn("real.ts", doc["changed_files"])
        self.assertFalse([f for f in doc["changed_files"] if "node_modules" in f])


class TestRefusals(Base):
    def test_missing_gates_file_refuses(self):
        p = run([str(self.wt), "--gates", str(self.wt / "nope.json")], self.wt)
        self.assertEqual(p.returncode, 2)

    def test_bad_scope_refuses(self):
        self.gates_file = self.gates([self.gate()])
        p = run([str(self.wt), "--gates", str(self.gates_file), "--scope", "sideways"], self.wt)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
