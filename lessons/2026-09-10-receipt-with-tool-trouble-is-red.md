# A receipt that mentions tool trouble is RED until re-run
Observed: an implementer reported typecheck clean and seven tests green while the file on disk held a duplicated block and did not compile; its editor state had diverged from disk and the receipt even said so.
Caught by: the verifier's independent re-run of the full bar.
Rule: the verifier re-runs every gate itself, always. Any receipt containing 'editor', 'could not run', 'state diverged' or similar is treated as a REJECT before reading further.
Evidence: legion-os-surveys FF-09 execution receipt.
