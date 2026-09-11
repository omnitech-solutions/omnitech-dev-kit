# Harnesses — one role contract, four adapters

The promptbooks, packets, receipts and config never change when the harness does. `scripts/run.py`
resolves the role's tools, approval, wall clock, model and thinking from `kit.config.json`, sets
`KIT_*` env vars, and executes `harness/<name>.sh` with the prompt parts (`@file` references and text).
Each adapter translates that contract into the harness's own flags. What cannot be translated is
stated here, not hidden.

| Contract item | omp (`omp -p`) | claude (`claude -p`) | codex (`codex exec`) | opencode (`opencode run`) |
| --- | --- | --- | --- | --- |
| No session | `--no-session` | print mode is sessionless | `--ephemeral` | **always persists**; tagged `--title "kit <role> <unit>"`, prune by hand |
| Tool allow-list | `--tools read,grep,glob,…` (exact) | `--allowedTools Read Grep …` (exact) | **none**; sandbox instead: `read-only` for r/o roles, `workspace-write` for writers | **none on the CLI**; `.opencode/agent/kit-<role>.md` `permission:` block (installed by `init_project.py`) |
| Approval | `--approval-mode always-ask\|yolo` | `--permission-mode plan\|default\|bypassPermissions` | `approval_policy="never"` (exec cannot answer prompts; the sandbox refuses) | agent `permission:` (`deny`/`ask`/`allow`) |
| Wall clock | `--max-time` **and** run.py | run.py only | run.py only | run.py only |
| Model | `--model provider/model` | `--model` (Anthropic only) | `-m` + `-c model_provider=…` (`KIT_CODEX_PROVIDER`) | `-m provider/model` |
| Reasoning | `--thinking low\|medium\|high` | not exposed | `-c model_reasoning_effort=…` | `--variant low\|medium\|high` |
| `@file` prompt parts | native | inlined by `_prompt.sh` | inlined by `_prompt.sh` | passed as `--file` |
| Final answer → `--out` | stdout stream | `result` of `--output-format json` | `-o <file>` | stdout stream |
| Cost source | OpenRouter key usage (`usage_probe: openrouter`) | `total_cost_usd` from the JSON result (`usage_probe: harness`) | OpenRouter key usage when routed through OpenRouter; else none | OpenRouter key usage when the model is `openrouter/…`; else none |
| Verified live | yes (pilot, 10 units) | dry-run only | dry-run only | dry-run only |

## Boundaries the adapters refuse to cross
- `codex.sh` never emits `danger-full-access`. `claude.sh` emits `bypassPermissions` only for `approval: yolo`,
  which the config gives only to roles that run inside a worktree.
- No adapter reads a key from a dotfile. The key is whatever env var `key_env` names, exported by the human.
- Guards (`exit 3` per-run, `exit 4` per-campaign, `exit 5` artefact invalid) are stops. Nothing retries.

## Setting each harness up once
- **omp**: `omp` on PATH, provider keys in omp's own auth. Skills: `python3 scripts/sync_skills.py` mirrors kit skills into `~/.omp/agent/skills/`.
- **claude**: `claude` on PATH, logged in. Install the kit as a plugin (README) so `CLAUDE_PLUGIN_ROOT` is set, or export `KIT_PLUGIN_ROOT`.
- **codex**: `codex` on PATH. For OpenRouter billing add to `~/.codex/config.toml`:
  ```toml
  [model_providers.openrouter]
  name = "OpenRouter"
  base_url = "https://openrouter.ai/api/v1"
  env_key = "OPENROUTER_API_KEY"
  ```
  and keep `harness_env.codex.KIT_CODEX_PROVIDER = "openrouter"` in `kit.config.json`. Skills for Codex live in `.agents/skills`; `sync_skills.py --target <repo>/.agents/skills` mirrors them.
- **opencode**: `opencode` on PATH with the OpenRouter provider configured. `init_project.py --harness opencode` installs `.opencode/agent/kit-*.md`; without those files the adapter warns and the run is **not** tool-restricted. Skills live in `.opencode/skills`.

## Adding a fifth harness
Write `harness/<name>.sh` that reads `KIT_ROLE KIT_UNIT KIT_TOOLS KIT_MAX_TIME KIT_APPROVAL KIT_MODEL KIT_THINKING KIT_OUT`,
sources `_prompt.sh`, maps what it can, prints what it cannot to stderr, calls `write_out` with the
final answer, and exits with the harness's code. Add the name to `HARNESSES` in `run.py`. Fill in a row above.
