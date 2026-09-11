# Timeouts, not tokens, are the main waste; change the prompt, never re-run it
Observed: every wasted dollar in a $0.98 pilot was a wall-clock kill: a reader sent to grep a 40k-line vendored bundle, an implementer running the full test bar inside its cap, a mid-tier planner that took 4-6 minutes on a three-file read while identical prompts elsewhere took 6-35 seconds.
Caught by: run.py's wall clock and the per-run cost column.
Rule: reader ≤5 named files and no generated bundles; implementer runs only the tests the packet names; verifier gets the full bar with a 9-12 minute cap; after ONE planner timeout, hand-write the packet if the evidence note already carries the design.
Evidence: legion-os-surveys FF-03 reader, FF-03 implementer, FF-06 and FF-05b orchestrators.
