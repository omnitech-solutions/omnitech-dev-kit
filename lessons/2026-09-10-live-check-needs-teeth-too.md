# A live check that passes before and after the fix has no teeth
Observed: a model-written browser check measured focus, which the browser already granted on mousedown, so it was green against the unfixed tree. The real signal was edit mode.
Caught by: a human asking 'what would make this red?' and running the check once against the unfixed tree.
Rule: every model-authored live check gets one human click-through and, when cheap, one run against the unfixed tree. verify-test-teeth applies to e2e checks, not only unit tests.
Evidence: legion-os-surveys FF-04 e2e extension.
