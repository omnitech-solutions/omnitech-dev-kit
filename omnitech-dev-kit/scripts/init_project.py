#!/usr/bin/env python3
"""init_project.py — scaffold one campaign folder for a feature in a consuming repo (stdlib only).

usage: init_project.py <repo> <campaign-dir> --feature <slug> [--harness omp|claude|codex|opencode]
                       [--models reader=M,orchestrator=M,implementer=M,verifier=M] [--baseline-usd N]
                       [--oracle "<what the oracle is>"] [--force]

Creates, without overwriting existing files unless --force:
  <campaign-dir>/
    OBJECTIVE.md            one paragraph: what done looks like, the oracle, the subject
    AGENTS-<feature>.md     the entry law, from promptbooks/AGENTS.template.md, slots marked <...>
    ledger.md               the single source of work: one row per observable behaviour
    kit.config.json         caps, harness, models, campaign id and baseline
    RUNBOOK.md              the five human-started commands for THIS harness, filled in
    fixtures/oracle/  fixtures/subject/  evidence/  packets/  receipts/  runs/
    spend.md  spend.jsonl
  <repo>/.opencode/agent/kit-*.md   (opencode only) role agents with tool permissions
Prints the checklist of what a human still has to fill in. Never touches git.
"""
import json, re, shutil, sys, time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent

def die(m, c=1): print(f"init_project.py: {m}", file=sys.stderr); sys.exit(c)

def write(path, text, force):
    if path.exists() and not force: return False
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text); return True

def main(a):
    if len(a) < 2: die(__doc__, 2)
    repo, camp = Path(a[0]).resolve(), Path(a[1])
    camp = camp if camp.is_absolute() else (repo / camp)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    feature = opt("--feature") or die("--feature <slug> required", 2)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", feature): die("feature slug must be kebab-case")
    harness = opt("--harness", "omp"); force = "--force" in a
    oracle = opt("--oracle", "<the oracle: the system whose behaviour is the target>")
    baseline = opt("--baseline-usd")
    models = {"reader": "openrouter/z-ai/glm-5.3-flash", "orchestrator": "openrouter/z-ai/glm-5.3",
              "implementer": "openrouter/z-ai/glm-5.3-flash", "verifier": "openrouter/z-ai/glm-5.3-flash"}
    for kv in (opt("--models", "") or "").split(","):
        if "=" in kv: k, v = kv.split("=", 1); models[k.strip()] = v.strip()
    if not repo.is_dir(): die(f"repo {repo} not a directory")
    today = time.strftime("%Y-%m-%d")
    rel = camp.relative_to(repo) if camp.is_relative_to(repo) else camp
    made = []

    cfg = json.loads((KIT.parent / "kit.config.example.json").read_text())
    cfg.update({"harness": harness, "campaign": f"{repo.name}/{feature}", "campaign_baseline_usd": float(baseline) if baseline else None,
                "models": models, "usage_probe": "harness" if harness == "claude" else "openrouter"})
    if write(camp / "kit.config.json", json.dumps(cfg, indent=2) + "\n", force): made.append("kit.config.json")

    agents = (KIT / "promptbooks" / "AGENTS.template.md").read_text().replace("<feature>", feature)
    if write(camp / f"AGENTS-{feature}.md", agents, force): made.append(f"AGENTS-{feature}.md")

    if write(camp / "OBJECTIVE.md", f"""# Objective — {feature}

Date: {today}. Oracle: {oracle}. Subject: <the system being changed, and where its current behaviour is captured>.

Done looks like: <one paragraph a stranger could verify>. Models never see the oracle directly; humans
freeze fixtures under `fixtures/oracle/` and `fixtures/subject/`, one pair per ledger row.

Out of scope for this campaign: <three things>.
""", force): made.append("OBJECTIVE.md")

    if write(camp / "ledger.md", f"""# Ledger — {feature}

Oracle: {oracle}
Subject: <url or path>

Verdicts: PASS / FAIL / PARTIAL / UNCAPTURED. Gate: the human review state of the unit.
Row ids: `{feature.upper()[:3]}-NN`. One row = one observable behaviour = at most one unit.

| id | behaviour | oracle fixture | subject fixture | verdict | unit | gate |
| --- | --- | --- | --- | --- | --- | --- |
| {feature.upper()[:3]}-01 | <behaviour in one sentence> | `fixtures/oracle/{feature.upper()[:3]}-01.md` | `fixtures/subject/{feature.upper()[:3]}-01.md` | UNCAPTURED | — | — |

Cap for this campaign: <N> rows. Extend by owner request only.
""", force): made.append("ledger.md")

    K = "$KIT_PLUGIN_ROOT"; B = "$B"; U = "$U"
    agents_ref = f"@{B}/AGENTS-{feature}.md"
    run = f"python3 {K}/scripts/run.py"
    runbook = f"""# RUNBOOK — {feature} ({harness})

Generated {today} by init_project.py. One unit at a time. Every arrow is a human gate.

```
capture fixtures (human)                       →  ledger row
  → reader       (r/o, cheap)                  →  evidence/<row>.md        [gate: cited? ≤5 files?]
  → orchestrator (r/o, mid)                    →  packets/<unit>.md        [gate: human edits, status REVIEWED]
  → git worktree add                           →  ../wt-<unit>
  → implementer  (worktree, rw)                →  receipts/<unit>-execution.md   (a CLAIM)
  → verifier     (worktree, r/o + bash)        →  receipts/<unit>-receipt.md     VERDICT
  → human live gate (re-capture + e2e)         →  commit from the main checkout, or reject
```

Shell setup (once per terminal):

```bash
export KIT_PLUGIN_ROOT={KIT}
export B={rel}          # campaign folder, relative to the repo root
export U=XX-01          # the unit you are working on
cd {repo}
```

Commands. Tools, approval mode, wall clock, model and thinking come from `kit.config.json` per role.

```bash
# 1 reader → evidence note (validated: six headings + at least one path:line)
{run} reader {U} . --out {B}/evidence/{U}.md --validate evidence -- \\
  {agents_ref} @{K}/promptbooks/read.md @{B}/fixtures/subject/{U}.md \\
  "Question: <one question, naming ≤5 files by path>"

# 2 orchestrator → packet (validated: 8 sections, §2 paths exist). Status stays DRAFT until you edit it.
{run} orchestrator {U} . --out {B}/packets/{U}.md --validate packet -- \\
  {agents_ref} @{K}/promptbooks/orchestrate.md @{K}/packets/TEMPLATE.md \\
  @{B}/fixtures/oracle/{U}.md @{B}/fixtures/subject/{U}.md @{B}/evidence/{U}.md "Write packet {U}."
# If the orchestrator times out once and the evidence note already carries the design, write the packet by hand.

# 3 worktree (implementer never runs in the main checkout)
git worktree add -b unit/{U} ../wt-{U} $(git branch --show-current)
# <project-specific: link or install dependencies inside the worktree; see AGENTS §gates>

# 4 implementer → execution receipt (a claim). Pass ONLY worktree-relative paths.
{run} implementer {U} ../wt-{U} -- \\
  {agents_ref} @{K}/promptbooks/implement.md @{B}/packets/{U}.md \\
  "Receipt path: {rel}/receipts/{U}-execution.md (relative to the worktree root). Run only the tests the packet names; leave the full bar to the verifier."

# 5 verifier → receipt (validated: VERDICT first line + gate lines)
{run} verifier {U} ../wt-{U} --out {B}/receipts/{U}-receipt.md --validate receipt -- \\
  {agents_ref} @{K}/promptbooks/verify.md @{B}/packets/{U}.md @{B}/receipts/{U}-execution.md \\
  @{K}/skills/borrowed/verify-test-teeth/SKILL.md @{K}/skills/borrowed/local-diff-review/SKILL.md \\
  @{K}/skills/borrowed/commit-scope-guard/SKILL.md @{K}/skills/borrowed/record-gate-evidence/SKILL.md \\
  "Receipt path: {rel}/receipts/{U}-receipt.md. Re-run every gate yourself."

# 6 human live gate, then apply: check `git status` in the MAIN checkout is clean first
git -C ../wt-{U} diff > /tmp/{U}.patch && git apply --3way /tmp/{U}.patch && git worktree remove ../wt-{U}
```

Before the first paid run: `{run} reader {U} . --dry-run -- {agents_ref} "x"` prints the resolved command.

Rules that are not optional (each one cost real money once; see `{K}/lessons/`):
- A model ACCEPT is a claim. The human live-boundary gate in the AGENTS file is what closes a row.
- Receipts that mention tool trouble, editor state, or "could not run" are RED until re-run.
- Never take live measurements while a verifier or e2e run is executing on the same machine.
- Reader questions name ≤5 files. Orchestrator prompts name exact line ranges or none.
- Implementers run only the tests the packet names; verifiers run the full bar with a 9–12 min cap.
- One timeout → change the prompt or write the artefact by hand. Never re-run the same prompt.
- Guards (exit 3/4) are stops. Do not raise a cap to make a run pass.
"""
    if harness == "opencode":
        runbook += f"""
OpenCode specifics: role agents live in `{repo}/.opencode/agent/kit-*.md` (installed by init_project.py).
Tool limits come from those files, not the CLI. Sessions persist; prune with `opencode session list`.
"""
    if harness == "codex":
        runbook += """
Codex specifics: there is no tool allow-list; read-only roles get `--sandbox read-only`, writing roles
`--sandbox workspace-write` in the worktree. To bill through OpenRouter define `[model_providers.openrouter]`
in ~/.codex/config.toml (base_url https://openrouter.ai/api/v1, env_key OPENROUTER_API_KEY) and set
`harness_env.codex.KIT_CODEX_PROVIDER` to `openrouter` in kit.config.json.
"""
    if harness == "claude":
        runbook += """
Claude Code specifics: bills the Anthropic account; `usage_probe` is `harness` and run.py records the
`total_cost_usd` the JSON result reports. OpenRouter models are not available here.
"""
    if write(camp / "RUNBOOK.md", runbook, force): made.append("RUNBOOK.md")

    if write(camp / "spend.md", f"""# Spend ledger — {feature} (USD)

Baseline key usage at campaign start ({today}): {baseline or '<fill from the usage probe before the first run>'}.
Guards: single run ≤ ${cfg['run_cap_usd']}; campaign total ≤ ${cfg['campaign_cap_usd']} above baseline. `run.py` appends one row per run.

| when | role | unit | wall | exit | run cost | key usage after | log |
| --- | --- | --- | --- | --- | --- | --- | --- |
""", force): made.append("spend.md")
    if write(camp / "spend.jsonl", "", force): made.append("spend.jsonl")
    for d in ["fixtures/oracle", "fixtures/subject", "evidence", "packets", "receipts", "runs"]:
        (camp / d).mkdir(parents=True, exist_ok=True); (camp / d / ".gitkeep").touch()

    if harness == "opencode":
        dst = repo / ".opencode" / "agent"; dst.mkdir(parents=True, exist_ok=True)
        for src in sorted((KIT / "templates" / "opencode" / "agent").glob("kit-*.md")):
            if write(dst / src.name, src.read_text(), force): made.append(f".opencode/agent/{src.name}")

    print(f"init_project: {camp}")
    for m in made: print(f"  created {m}")
    print("""
Human checklist before the first paid run:
  [ ] OBJECTIVE.md: replace every <...>
  [ ] AGENTS-<feature>.md: owned dirs, protected inputs, invariants, the gates table WITH baseline counts from a real run
  [ ] ledger.md: first 3–8 rows, each with an oracle and subject fixture you captured yourself
  [ ] kit.config.json: campaign_baseline_usd = current key usage; caps you can afford to lose
  [ ] export the API key env var in this shell (never in the kit, never in a dotfile grep)
  [ ] run.py --dry-run once; then the reader for row 1
  [ ] add the campaign folder to .gitignore or commit it — decide once, per repo""")

if __name__ == "__main__":
    main(sys.argv[1:])
