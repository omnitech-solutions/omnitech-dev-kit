# omnitech-dev-kit

One verified unit at a time, on cheap models, under guardrails.

You give it a **reference system** and **ours**, plus a ledger of differences you can *observe*.
It drives them to zero one unit at a time: a worker implements in a throwaway worktree, the gates
run deterministically, and nothing reaches a branch until a human has confirmed the behaviour with
their own eyes.

Measured on the loop this is extracted from: **10 units, $0.98 total, ~15 minutes each**, four of
which had a green model receipt over a broken page — caught every time by the live gate.

---

## The one command

```bash
kit next
```

That is the surface. It reads the ledger, finds the first row that is not PASS, does the next right
thing, and **stops at the next human gate**. Run it twice and it tells you the same thing twice.

| State | What it does | Who it stops for |
|---|---|---|
| no fixtures | tells you exactly what to capture, from both systems | **you** — models never open a browser |
| no packet | drafts `packets/<id>.md` from the template, lists the blanks | **you** |
| blanks left | lists them and refuses to spend a cent | **you** |
| not executed | worktree → implementer → gates → verifier *(the only paid step)* | — |
| not verified | prints the six verification steps | **you** |
| verified | commits and tags on the task branch | done |

---

## From nothing to a first accepted unit

```bash
cd <your repo>
export OPENROUTER_API_KEY=...                      # lives in ~/.zshrc; never in a config file

kit init parity \
  --oracle  "Qualtrics SV_xxx — observe-only, driven by the orchestrator" \
  --subject "http://127.0.0.1:5173/editor"

kit ledger add "hover greys the question text"     # one observable behaviour per row
kit next                                           # → tells you what to capture
#   … capture fixtures/oracle/R-01.md and fixtures/subject/R-01.md (measured values)
kit next                                           # → drafts the packet, lists the blanks
#   … fill them
kit next                                           # → runs the unit, then prints your checklist
#   … read the diff, mutation-test, check it live, write receipts/R-01-live.md
kit next                                           # → commits and tags
```

Everything lives in `.kit/<slug>/` as plain files you can read and edit without the tool.

---

## The five laws it enforces

Each was bought with real money.

1. **Models execute packets; they do not author them.** A model-written packet cost $0.12 and four
   minutes and came back empty. `kit next` drafts packets locally in 0 s for $0 and refuses to run a
   packet with unfilled blanks. *Packet precision is the cost control:* a precise packet lands for
   $0.05; a vague one cost **$1.03** and produced code that did not compile.
2. **A model's ACCEPT is a claim.** `kit accept` refuses without `receipts/<id>-live.md` carrying
   `LIVE: PASS` and an `evidence:` line, and refuses any diff touching a file outside packet §2.
3. **A default nobody chose is a bug.** Every role names its model or the run refuses (exit 11).
   Local models are refused unless opted in. The resolved model is printed on every run.
4. **The loop never blocks on its own ceremony.** Anomalies are recorded and printed; they never
   stop a later run. Nothing installs, bootstraps or migrates during a unit.
5. **Cheap by construction.** Per-run cap, wall clock, tool allow-list, named inputs, no session,
   one-turn prefetched verifier. Typical unit: implementer $0.02–0.04, verifier $0.01–0.02.

---

## Harnesses

`omp` (default, the proven path), `claude`, `codex`, `opencode` — one adapter each in `harness/`.
A role whose contract needs a capability a harness lacks refuses rather than silently degrading.
`kit doctor` reports what is installed. It is advisory and never blocks.

## crux

Optional and additive. If the repo has a crux tree, each accepted unit drops a note into
`<docs_dir>/inbox/` for `process-inbox` — crux's documented front door, never into the tree itself.
No crux tree means one advisory line and the records stay in the campaign folder.

## Layout

```
bin/kit          the entry point
kit/             run.py (admission) · unit.py (the four stages) · gates.py · accept.py
                 next_.py (the verb) · ledger.py · campaign.py · crux.py · cli.py
harness/         omp · claude · codex · opencode adapters
promptbooks/     WHO-YOU-ARE · implement · verify · ORCHESTRATOR
templates/       PACKET.md · config.json
tests/           34 tests, no mocks of the thing under test
```

Run the tests with `uv run --with pytest pytest -q`.
