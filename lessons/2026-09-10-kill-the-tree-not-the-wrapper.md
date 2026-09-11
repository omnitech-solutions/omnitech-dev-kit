# Terminating a wrapper does not terminate what it spawned
Observed: a wall-clock timeout returned 124 while the model process the adapter had started was still alive and still generating.
Caught by: an offline probe that timed out a sleeping fake model process and then checked whether it was still running.
Rule: start the adapter in its own process group, signal the whole group on timeout, and confirm it is gone before reporting. Fix this before introducing any concurrency, or a stopped run will keep running while its replacement starts. Note separately that killing local processes does not cancel remote generation or remote billing.
Evidence: omnitech-dev-kit v0.2.0 offline review, process-supervision probe.
