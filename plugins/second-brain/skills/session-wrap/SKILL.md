---
name: session-wrap
description: End-of-session housekeeping agent. Records the session's decisions and rationale, blockers, and next step; updates project todo, appends a daily vault entry, refreshes the project hub, updates project memory, logs lessons, and recommends the model for the next phase. Use when the user says "wrap session", "wrap up", "close out", "end session", "session wrap", "done for now", "that is it for today", "close this out", "wrap this up", any variation of ending a work session, OR when a Stop hook of your own injects a wrap reminder. Also runs in "backfill" mode from a pending-wraps ledger entry to reconstruct a wrap for a session that ended without one.
---

# Session wrap

Automate the four things that happen at the end of every Claude Code session: mark completed work in the todo, log what happened to the daily, update the project hub in the vault, and capture any lessons. Infers everything from conversation context. Does not ask the user to re-explain what was done.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable (`echo "$SECOND_BRAIN_VAULT"`). If it is unset or not a folder, say so and stop: never guess a vault path. Paths below that start with `Daily/`, `Tasks/`, `Projects/`, `Context/` or `Resources/` are relative to it.

## Required reads on trigger

1. `$SECOND_BRAIN_VAULT/CLAUDE.md` for vault routing and daily entry conventions.
2. The current working directory's `CLAUDE.md` or `PROJECT_RULES.md` for project identification.
3. `Context/voice-and-writing.md` in the vault, if it exists, for prose rules (the daily entry is written prose).

## Process

### Step 1: identify session work

Read the conversation history. Extract:

- What was built, fixed, deployed, or changed.
- Which files were created, modified, or deleted.
- Which project this work belongs to (derive from the working directory and any vault project references in the conversation).
- Whether any corrections from the user or gotchas were discovered (candidates for lessons.md).
- What the logical next step is (for the project hub's next_step field).

No user interaction. Infer from context.

If the session kept a ledger (`~/.claude/session-state/<session_id>.ledger.json`, the session-ledger skill), read it with `python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-ledger/scripts/ledger.py" --session <id> show`: its request, decisions (with their why) and open items are the wrap's primary source, and every open item is either resolved now or recorded under Open for the owner.

### Step 1.5: commit the session's repo work

If the working directory is a git repository **and is not the vault** (if the vault has its own sync or auto-commit job, that job owns vault commits; never double-commit there), check for uncommitted work from this session with `git status --porcelain`. If present, before logging anything: review the tree, stage only intended changes, split unrelated work into logical commits, and write Conventional Commit messages.

Rules:

- **Push only on a standing instruction.** Commit by default; push only where the owner has said pushes are wanted for that repo (for example, "push my own private repos"). For shared or collaboration repos (anything under another account or org, anything with PRs or review gates), commit only; pushing stays a deliberate act.
- **No repo at all is a finding, not a skip.** If the session produced work product in a folder with no git repo, flag it in the wrap report and offer to initialize a private per-project repo (`git init`, a `.gitignore` for node_modules/dist/env, `gh repo create <name> --private --source=. --push`). Do not silently leave new work untracked.
- **Patch-stage around parallel work.** If the tree holds changes this session did not make (a parallel session's edits), commit only what this session touched via `git add -p`, leave the rest, and name the leftover state in the daily entry.
- **Respect a standing do-not-commit.** If the user has said the repo is mid-refactor or holds deliberately uncommitted work, skip and record the uncommitted state under Open for the owner instead.
- If the tree is clean or the directory is not a repo, skip silently.

Why this step exists: session work left uncommitted goes stale invisibly and ends up tracked by memory. The wrap is the natural commit boundary.

### Step 2: update project-local todo

Read `tasks/todo.md` (or the project's equivalent task file) in the current working directory. For each task completed this session:

- Flip `- [ ]` to `- [x]`.
- If all items under an `## Active` section header are now checked, change `## Active` to `## Done`.
- Do not touch items that were not worked on this session.
- Do not restructure, reorder, or rewrite existing content.

If no project-local todo exists, skip this step silently.

### Step 3: update vault-level todo

Read `Tasks/todo.md` in the vault. Scan for items that match the work done this session. If matching items exist, check them off. If no matches, skip silently.

You may **add** items only when they are blockers or next-actions that surfaced this session and would otherwise be lost. Tag each with today's date. Do not add speculative or nice-to-have items; the vault todo is not a dumping ground. Blockers the next session must not miss belong in the todo, not just the daily prose.

### Step 4: append daily entry

Read `Daily/YYYY-MM-DD.md` in the vault (today's date).

- If the file exists, append the new session entry.
- If the file does not exist, create it with standard frontmatter (`type: daily`, `date: YYYY-MM-DD`, `status: active`, `tags: [daily]`), a `# YYYY-MM-DD` heading and a `## Log` section, and write the entry as the first content.

Entry format (the daily format in `Daily/CLAUDE.md`):

```
### {short summary of what was done} (Claude Code)

{Plain prose. What was built, changed, or shipped. Write every project and
person as an Obsidian wikilink (the name in double square brackets).
Sentence case in the heading.}

{Then, embedded in the prose or as trailing sentence-groups, three required
elements when the session was substantive:}

Decisions: {each load-bearing decision AND its rationale, not just the outcome.
"Chose X over Y because Z." A decision with no recorded why is half-logged.}

Open for the owner: {unresolved questions and blockers, the things the next
session or the owner must act on. If none, omit the group.}

{One closing line: context health + next-session model, from Step 7.}
```

Never overwrite or modify existing daily entries. Append only. The `## Log` section and the `# YYYY-MM-DD` heading are the file's structure; add your `###` entry under `## Log`, below the last entry.

### Step 5: update project hub

Identify the project hub file at `Projects/{Name}/{Name}.md` in the vault. The project name comes from the working directory name, the project's CLAUDE.md, or explicit references in the conversation. Common mappings:

- A working folder such as `~/alpha-site/` maps to `Projects/Alpha-Site/Alpha-Site.md`.
- Look for `aliases` or `workspaces` in the project hub frontmatter if the directory name does not match directly.

If the project hub is found:

1. Update `last_touched` in frontmatter to today's date (YYYY-MM-DD).
2. Update `next_step` in frontmatter to reflect what comes after the work done this session.
3. Add a dated bullet under `## Log` (or "Recent changes", whichever the hub uses) with a one-line summary. If that section has a date-stamped sub-heading, add a new entry under the current date heading.

If the project hub cannot be identified with confidence, say so in the summary. Do not guess.

### Step 6: log lessons (conditional)

If the session included corrections from the user, discovered gotchas, or earned new rules:

- **Recurrence check FIRST.** Before writing any new lesson from a correction, grep `Rules-of-Engagement.md` in the vault (and `Context/engineering-rules.md` and `Context/tech-stack.md` if the vault has them) for an existing rule that already covers it. If one exists, this is a RECURRENCE, not a new rule: append one JSON line to `Resources/operator/rule-recurrences.jsonl` in the vault, shaped `{"date": "YYYY-MM-DD", "rule": "<the rule's bold lead + its date tag>", "session": "<session_id or slug>", "note": "<one line: what happened>"}`, and do NOT restate the rule in the rules file or add a sibling bullet. (`vault-audit.py`'s `rule_rent` check reads this file; two recurrences flag the rule for hook or detector enforcement, because prose restatement has already failed twice by then.)
- Only when no existing rule covers it: append the lesson to the project-local `tasks/lessons.md` with the date and rule in imperative form.
- If the lesson applies broadly (not project-specific), also append to `Tasks/lessons.md` in the vault. A broadly-applying lesson does NOT get a `Rules-of-Engagement.md` bullet by default: a rule earns that seat only when it bites across several contexts, no hook or check can enforce it, and it has recurred or the owner promotes it. First offenses live in lessons.md.

If no lessons were earned and no recurrences were recorded, skip silently.

### Step 6.5: update project memory

The project's auto-memory lives at `~/.claude/projects/<slug>/memory/MEMORY.md` (the slug is the encoded working-directory path). Update it only with facts a **fresh session must know to act**: environment quirks, standing commands, decisions with a shelf life beyond ~2 weeks, and the pointer to the project hub. Never narrative history (that is the daily's job).

The vault-versus-ephemeral test: *will this matter in another session, or in 2+ weeks?* If yes, it goes to the vault (hub / lessons) or MEMORY.md; if no, let it die with the conversation. Keep MEMORY.md under ~200 lines; prune stale entries when you add new ones. If the project has no memory dir, skip silently.

### Step 6.7: capability harvest

Tested skills, hooks and executable workflows are more durable fixes than another lesson or memory entry; keep lessons as evidence, move repeatable procedures and enforceable checks into mechanisms that run. On timing: **one session can start a skill and the second hones it.** The ledger is `python3 "${CLAUDE_PLUGIN_ROOT}/operator/capability-candidates.py"` (it refuses out-of-order stages and writes `Resources/operator/capability-candidates.jsonl` in the vault).

1. **Name what this session reproduced.** A workflow qualifies only if it ran to a verified result this session (a test passed, a live check showed it), not if it was planned or half-done. An unverified workaround is never packaged.
2. **Improve before create.** Search the installed skills and the vault's `Skills/` folder for an existing skill that covers it. If one does and this session found its gap, fix that skill (with its own snapshot and test) and record `--stage drafted --target Skills/<existing>`.
3. **A new workflow is drafted, not shipped.** Create it in `Skills/_staging/<slug>/` in the vault with whatever skill-authoring skill you use, carrying a workflow contract: `## Trigger`, `## Inputs`, `## Prerequisites`, `## Procedure`, `## Outputs`, `## Failure handling`, and `## Verification` with a runnable command. Record `capability-candidates.py add --kind workflow --stage drafted --slug <slug> --session <id> --target Skills/_staging/<slug> --verify "<command>"`.
4. **A staged draft this session USED is honed.** If the session ran a `drafted` candidate's skill, fold in what the real run exposed, re-run its verification, and record `--stage honed` (the script refuses honing from the drafting session). A honed skill is reported to the owner as ready to promote; promotion is their call (`--by owner` only on their word).
5. **A recurring failure becomes a proposed mechanism.** When Step 6's recurrence check found a rule that failed again, or the session hit the same failure twice, propose the cheapest enforcing mechanism (a hook, then an audit check, then a skill trigger) and record `--kind failure --stage proposed --target "<mechanism>"`. Installing it is a standing change and needs the owner's word.
6. **Proportion.** Most sessions harvest nothing; skip silently. Never create a plugin per session: a new plugin only when the owner asks or a set of related skills has no home.

### Step 7: report + lifecycle

If you run session-lifecycle hooks of your own (none ship with this plugin), read this session's state file at `~/.claude/session-state/<session_id>.json` if present; such hooks typically record `compactions` and edit/turn counts. Without one, judge context health from what you observed in the session.

Determine the next phase's task type from the `next_step` just written, look it up in `references/model-guide.md`, and report:

```
Session wrapped.
- Todo: {checked off / added blockers / no changes}
- Commits: {N committed (subjects) / skipped: clean tree | vault | not a repo | do-not-commit standing}
- Daily: {entry appended to YYYY-MM-DD.md}
- Project: {hub updated / could not identify}
- Memory: {MEMORY.md updated / skipped}
- Lessons: {count / none}
- Capability: {drafted / honed / proposed (slugs) / none}
- Rule violations: {rule name, Nth recurrence, recorded to rule-recurrences.jsonl / none}
- Context: {"clean" | "compacted N time(s): <advisory>"}
- Next session: {model}, {one-clause reason from model-guide.md}

WRAP-COMPLETE {session_id}
```

**Before printing that report, touch the wrap sentinel:**

```bash
mkdir -p ~/.claude/session-state && touch ~/.claude/session-state/<session_id>.wrapped
```

This must be a real tool call, not a line of prose. A Stop hook **cannot see the assistant message that triggered it**: that message reaches the transcript after the hook has already run. So a prose marker alone is invisible at Stop time, and a hook that reminds about unwrapped sessions would nag every correctly wrapped one. A file written by a tool call is on disk before any hook reads. The sentinel costs nothing when no such hook is installed. If `session_id` cannot be determined, name the sentinel after the newest file in `~/.claude/session-state/` and say so in the report.

Rules for the last two lines:
- **Context health** from compactions: 0 = clean; 1 = "compacted once; wrap at the next milestone and consider a fresh session for architecture-grade work"; 2 or more = "recommend a fresh session now". Also flag fragmentation honestly if this session spanned two or more distinct projects or you noticed re-reading files you already read (post-compaction amnesia).
- **`WRAP-COMPLETE {session_id}`** is the fallback marker, readable by anything that scans a finished transcript (a SessionEnd hook, a backfill). Emit it verbatim as the last line, every successful wrap. Then, if `~/.claude/session-state/pending-wraps.jsonl` has an entry for this `session_id`, remove that line (the backfill is done).

## Rules

1. **Infer, do not interrogate.** The skill reads the conversation to determine what happened. It does not ask the user to re-explain. The user said "wrap up"; the skill wraps up.
2. **Never clobber existing content.** Todo items get checked, not rewritten. Daily entries get appended, not replaced. Project hubs get fields updated, not restructured.
3. **The vault's writing rules apply to the daily entry.** Sentence case headings. Obsidian wikilinks for projects and people. Read `Context/voice-and-writing.md` before writing if the vault has one.
4. **Fail gracefully on missing targets.** If there is no project-local todo, no vault todo match, or no identifiable project hub, skip that step and note it in the summary. Do not error out.
5. **One session, one entry.** Each invocation produces exactly one daily entry, one todo pass, and one project hub update. If the skill is triggered twice in the same session, the second run appends a second daily entry (it does not deduplicate).
6. **Corrections become rules.** When the user corrects this skill's output, record the correction in `Tasks/lessons.md` in the vault so the next wrap applies it.

## Modes

### Backfill wrap (from a pending-wraps ledger)

This mode needs a SessionEnd hook of your own that records sessions which ended without wrapping in `~/.claude/session-state/pending-wraps.jsonl` (fields: `session_id`, `date`, `cwd`, `transcript_path`, `edits`). No such hook ships with this plugin; without one the file never exists and this mode does not apply. To backfill an entry: read the named `transcript_path`, reconstruct the wrap from that transcript (lower fidelity than a live wrap, since you did not live the session), run Steps 2 to 7 against it, and mark the daily entry "(backfilled from transcript)". Remove the ledger line when done. Say plainly that it is a reconstruction.

When the transcript came from another surface (for example a Cowork session archived as markdown), tag the daily heading with that surface, as in `(Cowork, backfilled from transcript)`. The surface goes in the trailing `(<surface>)` position, never inside the title text, so per-surface counts can see it.

### Handoff on request only

Do **not** write handoff files by default: the Daily, project hubs, and project memory are the continuity layer. Only when the owner explicitly asks for a handoff, write it to the repo-local `<repo>/.claude/handoffs/` (permitted mid-refactor) or to `Resources/sessions/YYYY-MM-DD-{slug}.md` in the vault. Never as a standing wrap step.

## Edge cases

- **No todo file in the project.** Skip step 2. Note in summary.
- **Daily file does not exist yet.** Create it with frontmatter. Write the entry.
- **Multiple projects touched in one session.** Update each project hub separately. The daily entry can reference multiple projects.
- **Cannot determine the project hub path.** State this clearly in the summary. Suggest the likely path and ask the user to confirm for next time.
- **Session had no meaningful work.** If the conversation was purely exploratory or Q&A with nothing to log, say so. Do not fabricate entries.
- **Vault not mounted or paths unreachable.** Report which paths failed. Complete whatever steps are possible.

## Related

- `CLAUDE.md` at the vault root
- `Daily/CLAUDE.md`
- `Tasks/todo.md`
- `Projects/`
- `references/model-guide.md` in this skill
