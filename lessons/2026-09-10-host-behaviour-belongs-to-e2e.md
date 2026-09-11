# An assertion about what the HOST does belongs to e2e, not to a bare-model unit test
Observed: an implementer honestly reported a blocked assertion; it was a test-environment artefact because the bare framework model has no host governance.
Caught by: reading the receipt's blocked note instead of the green count.
Rule: when a packet asserts behaviour the host application applies, the unit test must build through the host path or the assertion moves to the live check. The receipt discipline (deviations written down, never silent) is what made this reviewable.
Evidence: legion-os-surveys FF-03b, FF-06b.
