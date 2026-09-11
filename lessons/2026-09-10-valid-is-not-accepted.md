# A valid document is not accepted work
Observed: the receipt validator accepted an ACCEPT that carried a failed gate line, and a receipt stating both verdicts at once. Meanwhile the canonical failing-gate line the gate helper emits was rejected by the same validator, so a truthful failure report could not be filed.
Caught by: an offline review that fed the validator contradictory documents.
Rule: shape validation must also check internal consistency - an ACCEPT contradicted by its own gate lines is invalid, an honest REJECT carrying a failed gate stays valid. And keep the categories separate: valid artefact, authentic gate execution, policy compliance, independent verification, human live acceptance. A green validator and a zero exit code prove invocation and shape, never acceptance.
Evidence: omnitech-dev-kit v0.2.0 offline review.
