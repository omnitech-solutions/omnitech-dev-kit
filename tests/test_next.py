"""`kit next` is a state machine that always stops at the next human gate — and never spends early.

Each test is one state transition from kit/next_.py's docstring. The load-bearing one is
test_model_accept_alone_commits_nothing: on 2026-09-10, four of nine units had a green model
receipt and a broken live page.
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
BIN = KIT / "bin" / "kit"


def kit(cwd, *args):
    return subprocess.run([str(BIN), *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "KIT_HARNESS": "omp"})


def repo():
    d = Path(tempfile.mkdtemp()) / "demo"
    d.mkdir(parents=True)
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    (d / "package.json").write_text('{"name":"demo","scripts":{"test":"echo 1 passed"}}')
    subprocess.run(["git", "-C", str(d), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@x",
                    "commit", "-qm", "init"], check=True, capture_output=True)
    return d


def campaign(d):
    kit(d, "init", "parity", "--oracle", "REF (observe-only)", "--subject", "http://localhost:1")
    return d / ".desoleary" / "kit" / "parity"


def test_next_without_campaign_explains_how_to_start():
    d = repo()
    r = kit(d, "next")
    assert r.returncode == 2 and "kit init" in r.stderr


def test_empty_ledger_asks_for_a_behaviour():
    d = repo(); campaign(d)
    assert "ledger is empty" in kit(d, "next").stdout


def test_missing_fixtures_stop_before_anything_is_drafted():
    d = repo(); c = campaign(d)
    kit(d, "ledger", "add", "hover greys the text")
    r = kit(d, "next")
    assert r.returncode == 2
    assert "fixtures missing" in r.stdout and "models never open a browser" in r.stdout
    assert not list((c / "packets").glob("*.md"))


def test_fixtures_present_drafts_a_packet_locally_and_lists_blanks():
    d = repo(); c = campaign(d)
    kit(d, "ledger", "add", "hover greys the text")
    (c / "fixtures" / "oracle" / "R-01.md").write_text("bg rgb(238,238,239)\n")
    (c / "fixtures" / "subject" / "R-01.md").write_text("bg transparent\n")
    r = kit(d, "next")
    assert r.returncode == 2 and "packet drafted (0s, $0)" in r.stdout
    assert (c / "packets" / "R-01.md").is_file()


def test_blanks_block_spending():
    """The $1.03 lesson: a packet with unfilled decisions must never reach a worker."""
    d = repo(); c = campaign(d)
    kit(d, "ledger", "add", "hover greys the text")
    (c / "fixtures" / "oracle" / "R-01.md").write_text("x")
    (c / "fixtures" / "subject" / "R-01.md").write_text("y")
    kit(d, "next")
    r = kit(d, "next")
    assert r.returncode == 2 and "blank(s)" in r.stdout
    assert not (c / "spend.jsonl").exists()


def _ready(d, c, receipt="VERDICT: ACCEPT\n\ngate: npm test exit 0 — pass\n"):
    import re
    kit(d, "ledger", "add", "hover greys the text")
    (c / "fixtures" / "oracle" / "R-01.md").write_text("x")
    (c / "fixtures" / "subject" / "R-01.md").write_text("y")
    kit(d, "next")
    p = c / "packets" / "R-01.md"
    p.write_text(re.sub(r"<[a-z][^>`]{2,}>", "filled", p.read_text()))
    (c / "receipts").mkdir(exist_ok=True)
    (c / "receipts" / "R-01-receipt.md").write_text(receipt)
    return p


def test_model_accept_alone_commits_nothing():
    d = repo(); c = campaign(d)
    _ready(d, c)
    before = subprocess.run(["git", "-C", str(d), "rev-list", "--count", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    r = kit(d, "next")
    assert r.returncode == 2
    assert "A model's ACCEPT is a claim" in r.stdout and "mutation test" in r.stdout
    after = subprocess.run(["git", "-C", str(d), "rev-list", "--count", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    assert before == after


def test_ledger_rows_round_trip():
    sys.path.insert(0, str(KIT))
    from kit import ledger as L
    d = repo(); c = campaign(d)
    L.add(c, "first behaviour")
    L.add(c, "second behaviour")
    assert [r["id"] for r in L.rows(c)] == ["R-01", "R-02"]
    assert L.next_open(c)["id"] == "R-01"
    L.set_verdict(c, "R-01", "PASS", unit="R-01", gate="live")
    assert L.next_open(c)["id"] == "R-02"
    assert [r["verdict"] for r in L.rows(c)] == ["PASS", "OPEN"]
