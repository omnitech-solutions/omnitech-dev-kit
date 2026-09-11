# A boundary the harness cannot enforce is not a boundary
Observed: a role declared read-only tools and the harness executed shell anyway, because that harness has no tool allow-list and expresses limits only through a sandbox. Another harness fell back to an unrestricted default agent when its role file was missing, and warned instead of refusing. A third was passed a flag that waives permission prompts in place of the flag that actually restricts the tool set.
Caught by: reading the run log of a role that was supposed to have no shell, and reading each CLI's own reference for what its flags do.
Rule: record what each harness can actually make impossible, and refuse a role whose contract it cannot meet. An accepted gap must be written down in config, per harness, as a deliberate decision. Missing restrictions must prevent launch, never degrade to a warning.
Evidence: kit-trial TRIAL-codex log; opencode adapter fallback; claude --allowedTools vs --tools.
