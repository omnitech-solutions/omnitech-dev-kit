#!/usr/bin/env python3
"""cli.py — the dispatcher. Deliberately stupid: it parses argv and calls one function.

    kit install [--with-rulesync]                  FIRST in any repo: overlay, commands, ignores
    kit next [--row ID] [--campaign DIR] [--dry]   the only verb you need
    kit init <slug> --oracle "..." --subject "..." scaffold a campaign here
    kit ledger add "<behaviour>" [--id ID]         add one observable row
    kit status                                     ledger, spend, what is waiting on you
    kit accept <row>                               commit + tag (kit next does this for you)
    kit unit <row>                                 execute one packet (kit next does this for you)
    kit gates [--scope selected|full] [--detect]   deterministic gates, no model
    kit run <role> <unit> <cwd> -- @file "..."     one guarded model call
    kit doctor                                     advisory environment report, never blocks
"""
import json, os, subprocess, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent


def _opt(a, name, default=None):
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def main(argv):
    a = list(argv)
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, rest = a[0], a[1:]
    campaign = _opt(rest, "--campaign")
    harness = _opt(rest, "--harness", os.environ.get("KIT_HARNESS", "omp"))

    if cmd == "next":
        from .next_ import cmd_next
        return cmd_next(campaign, harness, _opt(rest, "--row"), run="--dry" not in rest)

    if cmd == "install":
        from .install import cmd_install
        return cmd_install(_opt(rest, "--repo"), "--with-rulesync" in rest)

    if cmd == "init":
        from .init_campaign import cmd_init
        slug = next((x for x in rest if not x.startswith("--") and x not in
                     {_opt(rest, "--oracle"), _opt(rest, "--subject"), campaign, harness}), None)
        if not slug:
            print('usage: kit init <slug> --oracle "<reference system>" --subject "<ours>"', file=sys.stderr)
            return 2
        return cmd_init(slug, _opt(rest, "--oracle", ""), _opt(rest, "--subject", ""), harness)

    if cmd == "ledger":
        from . import ledger as L
        from .campaign import newest_campaign, repo_root, die
        repo = repo_root() or die("not inside a git repository")
        camp = Path(campaign).resolve() if campaign else newest_campaign(repo, None)
        if camp is None:
            print("no campaign; run `kit init` first", file=sys.stderr)
            return 2
        if rest[:1] == ["add"]:
            beh = next((x for x in rest[1:] if not x.startswith("--")), None)
            if not beh:
                print('usage: kit ledger add "<one observable behaviour>"', file=sys.stderr)
                return 2
            row = L.add(camp, beh, _opt(rest, "--id"))
            print(f"{row['id']}  {row['behaviour']}")
            return 0
        for r in L.rows(camp):
            print(f"{r['verdict']:8s} {r['id']:8s} {r['behaviour'][:70]}")
        return 0

    if cmd == "status":
        from .status import cmd_status
        return cmd_status()

    if cmd == "accept":
        from .accept import cmd_accept
        row = next((x for x in rest if not x.startswith("--")), None)
        if not row:
            print("usage: kit accept <row>", file=sys.stderr)
            return 2
        return cmd_accept(row, campaign)

    if cmd == "unit":
        from .next_ import cmd_next
        row = next((x for x in rest if not x.startswith("--")), None)
        return cmd_next(campaign, harness, row, run=True)

    if cmd in ("gates", "verify"):
        script = KIT / "kit" / ("detect_gates.py" if "--detect" in rest else "gates.py")
        return subprocess.run([sys.executable, str(script)] + [x for x in rest if x != "--detect"]).returncode

    if cmd == "run":
        return subprocess.run([sys.executable, str(KIT / "kit" / "run.py")] + rest).returncode

    if cmd == "doctor":
        from .doctor import cmd_doctor
        return cmd_doctor()

    print(f"unknown command {cmd!r}\n\n{__doc__.strip()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
