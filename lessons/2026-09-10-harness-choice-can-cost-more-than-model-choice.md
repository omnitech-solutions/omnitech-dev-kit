# The harness, not the model, can drive a 9x cost difference on identical work
Observed: the same reader question, same model, same three files cost $0.0041 through one harness and $0.0385 through another. The expensive one has no tool allow-list, so the model shelled out and dumped all three files with line numbers several times over.
Caught by: running one question through every harness and comparing the spend rows side by side.
Rule: before adopting a harness for a role, run one identical unit through it and compare cost and wall time, not just whether it works. A harness that cannot restrict tools lets the model choose an expensive way to do a cheap thing.
Evidence: kit-trial TRIAL-omp vs TRIAL-codex.
