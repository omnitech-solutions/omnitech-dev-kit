"""`kit accept` is the only thing that commits, and it refuses three ways.

Live-gate refusal is the mechanism behind law 2: a worker's ACCEPT never reaches the branch
without a human's own live evidence.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
BIN = KIT / "bin" / "kit"
PACKET = """# Packet R-01 — demo

Status: REVIEWED (human)

## 2. Owned files (EXCLUSIVE)
- `src/a.txt` — the change
"""


def fixture(live=None, receipt="VERDICT: ACCEPT\n\ngate: npm test exit 0 — pass\n", stray=False):
    root = Path(tempfile.mkdtemp())
    d = root / "demo"; d.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=False, capture_output=True)
    (d / "src").mkdir(); (d / "src" / "a.txt").write_text("before\n")
    git("add", "-A"); git("-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "init")
    c = d / ".desoleary" / "kit" / "parity"
    for s in ("packets", "receipts"):
        (c / s).mkdir(parents=True)
    (c / "config.json").write_text('{"live_gate": true, "crux": {"enabled": false}}')
    (c / "packets" / "R-01.md").write_text(PACKET)
    (c / "receipts" / "R-01-receipt.md").write_text(receipt)
    if live is not None:
        (c / "receipts" / "R-01-live.md").write_text(live)
    wt = d.parent / "wt-parity-R-01"
    subprocess.run(["git", "-C", str(d), "worktree", "add", "-q", str(wt), "-b", "kit/parity-r-01"],
                   capture_output=True)
    (wt / "src" / "a.txt").write_text("after\n")
    if stray:
        (wt / "outside.txt").write_text("not in section 2\n")
    return d, c, wt


def accept(d):
    return subprocess.run([str(BIN), "accept", "R-01", "--campaign", str(d / ".desoleary" / "kit" / "parity")],
                          cwd=d, capture_output=True, text=True, env={**os.environ})


def committed(wt):
    return subprocess.run(["git", "-C", str(wt), "rev-list", "--count", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def test_refuses_without_a_live_receipt():
    d, c, wt = fixture(live=None)
    before = committed(wt)
    r = accept(d)
    assert r.returncode == 6, r.stderr
    assert "live" in (r.stderr + r.stdout).lower()
    assert committed(wt) == before


def test_refuses_a_live_receipt_with_no_evidence():
    d, c, wt = fixture(live="LIVE: PASS\n\nlooked fine\n")
    r = accept(d)
    assert r.returncode == 6 and committed(wt) == "1"


def test_refuses_a_non_accept_receipt():
    d, c, wt = fixture(live="LIVE: PASS\nevidence: measured bg rgb(238,238,239)\n",
                       receipt="VERDICT: REJECT\n\nthe test has no teeth\n")
    r = accept(d)
    assert r.returncode == 2 and committed(wt) == "1"


def test_refuses_a_scope_breach():
    d, c, wt = fixture(live="LIVE: PASS\nevidence: measured bg rgb(238,238,239)\n", stray=True)
    r = accept(d)
    assert r.returncode == 4 and "outside" in (r.stderr + r.stdout)
    assert committed(wt) == "1"


def test_commits_and_tags_when_everything_is_in_order():
    d, c, wt = fixture(live="LIVE: PASS\nevidence: measured bg rgb(238,238,239)\n")
    r = accept(d)
    assert r.returncode == 0, r.stderr + r.stdout
    assert committed(wt) == "2"
    tags = subprocess.run(["git", "-C", str(wt), "tag"], capture_output=True, text=True).stdout
    assert "kit/parity-R-01-after" in tags or "kit/parity-r-01-after" in tags
