# Absolute paths in receipts leak edits into the main checkout
Observed: an implementer confined to a worktree edited the main checkout as well, because an earlier receipt it read contained absolute paths to main.
Caught by: a human git status in main before applying the patch.
Rule: prompts and receipts carry worktree-relative paths only. Before every apply-to-main, check that main is clean. commit-scope-guard on the worktree cannot see edits made elsewhere.
Evidence: legion-os-surveys FF-09.
