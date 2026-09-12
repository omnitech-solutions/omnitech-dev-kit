"""Nothing is lost when a worker is stopped, and the main checkout is never touched.

Both behaviours come from real incidents:

  * A worker killed by the wall clock cannot write packet §7's checkpoint — it is already dead. So
    the kit writes it, from facts it has: exit reason, worktree, diff stat, files, log tail.
  * FF-09 (2026-09-10): an implementer edited the MAIN checkout as well as its worktree, because
    absolute paths leaked in from a receipt it had read.
  * FF-09 again: a receipt claimed "typecheck clean, 7 tests green" while the file on disk did not
    compile; the receipt itself admitted its editor state had "diverged from disk".
"""
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from kit.unit import host_status, incomplete_receipt, receipt_trouble  # noqa: E402


def repo_and_worktree():
    root = Path(tempfile.mkdtemp())
    d = root / "demo"
    d.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
    subprocess.run(["git", "-C", str(d), "init", "-q"], capture_output=True)
    (d / "src.txt").write_text("before\n")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "init")
    wt = root / "wt-demo"
    git("worktree", "add", "-q", str(wt), "-b", "kit/demo")
    camp = d / ".desoleary" / "kit" / "c"
    (camp / "receipts").mkdir(parents=True)
    (camp / "runs").mkdir(parents=True)
    return d, camp, wt


def test_partial_work_is_recorded_when_the_worker_is_killed():
    d, camp, wt = repo_and_worktree()
    (wt / "src.txt").write_text("90 percent of an implementation\n")
    (wt / "new.ts").write_text("export const x = 1\n")
    f = incomplete_receipt(camp, d, wt, "U-01", "implementer", 124, "…last tool call: edit new.ts")
    body = f.read_text()
    assert body.startswith("STATUS: INCOMPLETE (implementer stopped by wall clock)")
    assert "is NOT lost" in body
    assert "src.txt" in body and "new.ts" in body          # both the edit and the new file
    assert "kit next" in body and "checkout --" in body     # resume and discard, both offered
    assert "last tool call" in body                         # the log tail survived


def test_the_partial_work_itself_survives_on_disk():
    """The receipt is a pointer; the worktree is the thing. It must still be there."""
    d, camp, wt = repo_and_worktree()
    (wt / "src.txt").write_text("90 percent\n")
    incomplete_receipt(camp, d, wt, "U-01", "implementer", 124)
    assert (wt / "src.txt").read_text() == "90 percent\n"
    diff = subprocess.run(["git", "-C", str(wt), "diff", "--stat"], capture_output=True, text=True).stdout
    assert "src.txt" in diff


def test_host_checkout_fingerprint_detects_contamination():
    d, camp, wt = repo_and_worktree()
    before = host_status(d)
    (wt / "src.txt").write_text("worker edits its own worktree\n")
    assert host_status(d) == before, "a worktree edit must not register as main changing"
    (d / "src.txt").write_text("a worker reached into main\n")
    assert host_status(d) != before, "an edit to main must be detected"


def test_receipt_mentioning_tool_trouble_is_flagged():
    d, camp, wt = repo_and_worktree()
    (camp / "receipts" / "U-01-execution.md").write_text(
        "typecheck clean, 7 tests green.\nNote: my editor state diverged from disk.\n")
    assert "diverged" in receipt_trouble(camp, "U-01")


def test_a_clean_receipt_is_not_flagged():
    d, camp, wt = repo_and_worktree()
    (camp / "receipts" / "U-01-execution.md").write_text("typecheck clean, 7 tests green.\n")
    assert receipt_trouble(camp, "U-01") == []
