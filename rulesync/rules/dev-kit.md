# omnitech-dev-kit is how verified change happens in this repository

This repository runs a dev-kit campaign: `.kit/<slug>/` holds a ledger of observable differences
between a reference system and ours, plus the packets, fixtures, receipts and spend for each one.

**Use `kit next`.** It is the only command you need. It reads the ledger, does the next right thing
for the first row that is not PASS, and stops at the next human gate. It is idempotent — running it
twice tells you the same thing twice — so when in doubt, run it and read what it says.

Do not hand-roll the loop. Do not ask a model to write a packet. Do not commit a unit yourself.

## The three rules that are not advisory

1. **Models execute packets; they never author them.** `kit next` drafts a packet locally in zero
   seconds for zero dollars and refuses to spend while it still has `<…>` blanks. Filling those
   blanks precisely is the single biggest cost lever: a precise packet lands for about $0.05; a
   vague one has cost $1.03 and produced code that did not compile.
2. **A worker's ACCEPT is a claim, not a result.** Before anything is committed, read the gate
   record, read the diff against packet §2, read the test, mutation-test it (break the change and
   the test must go red, then restore byte-identical), and confirm the behaviour yourself on the
   running system. Record that in `receipts/<id>-live.md`. `kit accept` refuses without it.
3. **The reference system is observe-only.** Never send, publish, save, delete or change settings
   on it. Capture measured values — computed styles, DOM counts, geometry — never impressions.

Workers run in throwaway worktrees and never touch the primary checkout. If work would touch a file
outside the packet's owned files, stop and say so rather than widening the scope.
