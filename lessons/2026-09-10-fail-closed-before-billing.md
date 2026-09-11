# Fail closed before billing: validate tool names, files and shapes locally
Observed: an invalid tool name made the harness exit before any request was billed ($0); a prompt with a missing @file would have burned a run explaining the absence.
Caught by: the harness's own validation, then run.py's pre-flight.
Rule: every check that can run without a model runs before the model: prompt files exist, role is in config, artefact shape validates after the run. A failed validation is a failed run (exit 5), not a note.
Evidence: legion-os-surveys FF-01 first reader row at $0.
