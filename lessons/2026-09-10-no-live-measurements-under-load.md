# Never take live measurements while a verifier or e2e run is executing
Observed: a 'UI freezes during autosave' report (45-second stalls) reproduced only while a unit-test run and a browser e2e run shared the machine; alone, autosave took 29-215 ms with zero long tasks. A row was almost opened for a defect that did not exist.
Caught by: instrumenting with a long-task observer and a timed save wrapper, then re-measuring on a quiet machine.
Rule: queue human re-captures and performance measurements after the gates finish. A two-minute instrumentation probe beats an hour of theorising.
Evidence: legion-os-surveys FF-08, closed at $0.
