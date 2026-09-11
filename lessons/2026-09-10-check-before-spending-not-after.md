# Guards that fire after the run are reports, not limits
Observed: the per-run and per-campaign dollar checks ran after the model had already been paid for, so a campaign already over its cap could still start one more run and only then report the overrun.
Caught by: an offline review reproducing the control flow with mocked usage.
Rule: every locally decidable check runs before the adapter is launched - budget admission, metering, capability, workspace identity, option combinations, context size. Keep the post-run checks, but name them overrun reports so nobody mistakes them for prevention.
Evidence: omnitech-dev-kit v0.2.0 offline review.
