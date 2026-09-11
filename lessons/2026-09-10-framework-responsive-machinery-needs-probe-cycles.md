# Changes that lean on a framework's responsive or lifecycle machinery need a probe-fix-probe budget
Observed: a correct packet still needed three human fix loops because the framework gated header folding behind selection, never re-measured a fixed-width bar, and rebuilt overflow entries from each action's original data. None of that was knowable from the evidence note.
Caught by: probing the live model in the browser console between runs.
Rule: when a packet touches framework lifecycle, responsiveness or dev-mode remount behaviour, budget for a live probe cycle and keep model runs cheap so the cycle stays affordable. When order-of-events is the suspect, instrument and read the timeline before theorising.
Evidence: legion-os-surveys FF-05, FF-07.
