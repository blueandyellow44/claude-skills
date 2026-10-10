---
name: canon-health
description: >-
  Diagnostic audit of the always-loaded canon's size, rule count, growth,
  recurrence data, and retrieval reliability, judged against the
  instruction-following evidence (adherence degrades past ~150-200 discrete
  rules; count is the operative unit, not chars; omissions dominate). Produces
  a ranked verdict in chat and routes over-budget findings to canon-slim.
  Diagnoses only - never edits canon. Triggers on 'canon health', 'is the ROE
  slim enough', 'roe effectiveness', 'rule budget check', 'audit the canon',
  'is the canon too big', 'instruction budget'.
---

# canon-health

You are running canon-health. It answers ONE question with evidence: **is the
always-loaded canon sized and structured for reliable execution?** It never edits
canon. Over-budget findings route to `canon-slim` (the executor); recurring rules
route to hook enforcement, which the owner installs.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the
audit stops with a message when it is unset.
`AUDIT="${CLAUDE_PLUGIN_ROOT}/skills/vault-setup/references/operator/vault-audit.py"`
(or the vault's own copy at `Resources/operator/vault-audit.py`).

## The evidence baseline (cite it, do not re-derive it)

- **Count is the operative unit, not chars.** Frontier models hold near-perfect
  adherence up to ~150-200 discrete instructions, then degrade; Claude models decay
  LINEARLY (every added rule costs adherence, no free plateau). Best models hit only
  ~68% at 500. (IFScale, arXiv 2507.11538)
- **Failures are omissions**: at density, rules are silently ignored, not misapplied.
- **Primacy bias peaks at 150-200**: models favor earlier rules under load. A
  non-negotiables-first ordering is load-bearing; keep the most important rules first.
- **Hierarchy + selective retrieval beat flat in-context loading** (arXiv 2510.11588).
  The vault's answer: a short always-loaded rules file, the full story in
  `Tasks/lessons.md`, and mechanisms (hooks, audit checks, skills) for what prose
  cannot hold.
- Anthropic: "Bloated CLAUDE.md files cause Claude to ignore your actual
  instructions... delete it or convert it to a hook."
- Re-verify these numbers against current research roughly every 6 months; the
  constants in `vault-audit.py` (ROE_RULE_COUNT_BUDGET, CANON_BUDGETS,
  CANON_FLOW_MAX_GROWTH) are the operational form and stay in sync with what the
  research supports.

## Procedure

1. **Stock**: `python3 "$AUDIT" --only canon_budgets,canon_rule_count,canon_flow,rule_rent,roe_sunset`. This is the deterministic core; the skill interprets, the detectors measure.
2. **The whole always-loaded stack**, not just the rules file: sizes and rule counts (`- **` + numbered bullets) for `Rules-of-Engagement.md`, the vault's root `CLAUDE.md`, `~/.claude/CLAUDE.md` and every file it imports, plus anything a session-start hook of yours injects. Sum the discrete directives and place the total against the 150-200 knee. The harness's own system prompt spends part of the budget too; say so.
3. **Retrieval reliability** (displacement is only safe while this holds): a displaced rule must still be findable when it matters. If the vault runs retrieval hooks with tests, run those tests; any red case is a P1 finding. If it runs none (none ship with this plugin), say so plainly: displaced rules are then reached only when a session greps `Tasks/lessons.md`, which is the weaker guarantee, and the verdict must weigh it.
4. **Effectiveness data**: read `Resources/operator/rule-recurrences.jsonl` in the vault. Any rule at 2+ recurrences is a hook-candidate (prose has failed twice). Cross-check the `roe_sunset` list for displacement candidates. If the file is empty after weeks of sessions, suspect the instrument (session-wrap Step 6 writes it), not perfect compliance: a permanently clean log means the probe points at the wrong thing.
5. **Verdict in chat**: ranked issues, then ranked levers, each tied to a number from steps 1-4. The lever hierarchy, best first: **merge rules** (buys adherence), then **displace to a second tier / retrieval**, then **convert to hook/detector**, then compress wording (buys almost nothing; the compression well is usually dry). Steel-man the status quo: conditional rules are mostly dormant per-prompt, so effective simultaneous load is below the raw count; the knee is a floor-of-concern, not a cliff.
6. **Route, never execute**: over-budget, name `canon-slim` and stop; recurring rule, propose the hook and stop; retrieval red, fix retrieval BEFORE any further displacement is proposed. Standing changes are proposed and installed on the owner's word.

## Rules

1. Diagnosis only. This skill never edits the rules file, canon files, budgets, or hooks.
2. Report only what was measured; a number not produced by a step above is not in the verdict.
3. Every threshold cited comes from the constants in `vault-audit.py` or the named research, never from memory of this file's prose alone.
4. The primary deliverable is the verdict on the CANON; retrieval and recurrence data are validation layers, not the subject.

## Related

- `canon-slim`: the executor this skill routes to
- `vault-audit.py`: the detectors (canon_budgets, canon_rule_count, canon_flow, rule_rent, roe_sunset)
