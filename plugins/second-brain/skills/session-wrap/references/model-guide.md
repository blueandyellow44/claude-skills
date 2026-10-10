# Model guide: which model for the next phase of work

Read by `session-wrap` Step 7 to emit a `Next session: <model>, <reason>` line.
Update this table as models and pricing change; it is the single source for the
recommendation. Current models (2026-07): Fable 5, Opus 4.8, Sonnet 5, Haiku 4.5.
The `[1m]` suffix means the 1-million-token context variant.

| Next-phase task type | Recommended | Why |
|---|---|---|
| Architecture / system design | Fable 5 (Opus 4.8 ok) | Deepest reasoning; use `[1m]` when the design corpus must stay whole in one window |
| Planning | Fable 5 | Same judgment load as architecture |
| Implementation, well-specified | Sonnet 5 | Strong coder, fast, cheap; escalate to Fable/Opus for cross-cutting refactors |
| Debugging, gnarly / multi-system | Fable 5 or Opus 4.8 | Hypothesis discipline; a simple repro drops to Sonnet 5 |
| Writing in the owner's voice | Fable 5 | Highest judgment load in the system; Opus 4.8 second |
| Auditing | Opus 4.8 or Fable 5, a *different* model than the one that produced the work | Fresh-eyes rule; the maker is the wrong judge |
| Code review | Same as auditing | Different model than the author |
| Research / synthesis | Sonnet 5 default; Fable 5 `[1m]` when >~200k tokens of sources must coexist | |
| Mechanical bulk (backfills, renames, format passes) | Haiku 4.5 | Cost floor; zero judgment |

## Rules for the recommendation

- Derive the next-phase task type from the `next_step` the wrap just wrote to the
  project hub. If it is ambiguous, say so and give the top two.
- The audit/review rows are the one place model *identity* matters: never
  recommend the same model that authored the work under review. If this session
  wrote the code, recommend a different model to review it.
- This is a default, not a mandate. The owner overrides freely; the line exists to make
  the choice deliberate, not automatic.

## Effort vocabulary by surface

Claude Code and Codex do not share effort-level names. As verified against the
installed Claude Code 2.1.226 CLI on 2026-08-08, Claude Code accepts `low`,
`medium`, `high`, `xhigh`, and `max`; its strongest session setting is
`--effort max`. `ultrareview` is a separate cloud-hosted multi-agent review
command, not an effort level. Never translate Codex's `ultra` label into a
Claude Code recommendation. Check the live CLI help again after an upgrade
before naming a setting.
