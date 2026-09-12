# After `kit go` — what the orchestrator does, and nothing else

The worker's ACCEPT is a claim. You close the unit. Spend your tokens on these six steps only; everything
else (the packet, the worktree, the gates, the verifier, the inbox drop) the kit already did.

1. **Read the gate record** (`gates-run-<unit>.json`, ≤30 lines): every gate `pass` or `no_regression`
   at selected scope. A `regression` is a REJECT before you read any code.
2. **Read the diff** (`receipts/<unit>.diff`) against §2 of the packet. Any file outside §2 → REJECT
   (scope breach), even if the change is good. Diff over ~300 lines → the packet was too big; split it.
3. **Read the test, not the receipt.** The §5 test must assert the behaviour against the real artefact
   — no mocks, no monkeypatching, no `assert True`. A test that would pass without the change is not a test.
4. **Mutation-test once.** The worker's change is UNCOMMITTED in the worktree, so `git checkout -- <file>`
   would erase it (it did, once). Save first: `cp <wt>/<file> /tmp/<file>.keep`; break the change (flip one
   condition), run only the §5 test, expect RED; restore with `\cp -f /tmp/<file>.keep <wt>/<file>`, confirm
   `git -C <wt> diff --stat` is unchanged, expect GREEN. If it stays green, REJECT: the test has no teeth.
   (If you do lose the change: the kit saved `receipts/<unit>.diff`; `git -C <wt> apply` it.)
5. **Accept or reject.**
   - Accept: `git -C <wt> add -A && git -C <wt> commit -F -` (say what and why, cite the gate record), then
     `git tag kit/<campaign>-<unit>-after`. The next unit chains from this branch.
   - Reject: write two lines in `receipts/<unit>-receipt.md` under `VERDICT: REJECT` (what, evidence),
     `kit acknowledge` if an anomaly was raised, and either fix the packet and `kit go` again or drop the unit.
6. **Check the two targets** printed by `kit status`: ≤15 min, ≤$0.15. Over either → the packet was
   wrong-sized or the worker wandered; record why in one sentence in the next packet's Evidence line.

Never: type the implementation yourself, run the full gate bar in-context, raise a cap to make a run pass,
re-run the same prompt after a timeout, or let a worker touch the primary checkout. Qualtrics and every
other live system are observe-only — no sends, no publishes, no saves.
