# A measurement that failed is not a zero
Observed: a missing metering key let a run start and recorded its cost as $0.00; an exception in the post-run usage probe could lose the spend row entirely; and a harness that reports its own cost never contributed to the campaign total at all.
Caught by: an offline review of the runner's control flow, reproduced with mocked usage values.
Rule: refuse to start a run that cannot be measured unless unmetered spend is accepted deliberately in config. Write a durable start record before launching and finalise it on every exit path. Carry an explicit cost_known flag, exclude unknown rows from totals, and count them separately.
Evidence: omnitech-dev-kit v0.2.0 offline review, findings on metering and accounting.
