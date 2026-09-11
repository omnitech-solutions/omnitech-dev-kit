# A model that repeats one tool call has usually lost its instructions to context truncation
Observed: a local 30B coder model re-read the same file 30 times and produced nothing, twice, until the wall clock killed it. The runtime log showed a 51,703-token prompt with 50,925 tokens removed from the middle. Each repeated read appended the whole file again, the window overflowed, truncation deleted the instructions, and the model restarted from its opening sentence.
Caught by: the run log (same tool line repeated, no output sections) and the runtime's own truncation notice.
Rule: declare each model's context window in config and refuse a prompt that would not fit; watch the log during the run and kill at the Nth identical tool call rather than waiting out the cap. Free local models are not cheap: they spend wall clock instead of money. Never re-run a looping prompt unchanged.
Evidence: legion-os-surveys kit-trial TRIAL-opencode and TRIAL-opencode-R2.
