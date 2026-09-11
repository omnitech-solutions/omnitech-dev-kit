# A model ACCEPT is a claim until the live-boundary gate passes
Observed: a verifier accepted a unit whose tests (650+) were green while the shipped UI had zero live handlers; framework dev-mode double-mounting disposed the wiring after the first render. Four of ten units in the pilot had a model-level ACCEPT that was wrong at the live boundary.
Caught by: the human fixture re-capture and the browser end-to-end parity run, both mandatory gates after the verifier.
Rule: the definition of done names a live-boundary check that a model does not run. An ACCEPT receipt says 'owed: human' until that check passes. Never write 'done' from a model verdict.
Evidence: legion-os-surveys FF-01-R1, FF-03b, FF-04, FF-07 receipts.
