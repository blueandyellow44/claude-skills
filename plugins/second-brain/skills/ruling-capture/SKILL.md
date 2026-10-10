---
name: ruling-capture
description: "Write the owner's ruling down the same turn they make it, in ANY project: verbatim and dated, into that project's hub Rules section and its project-memory current-rules file, and mark what it supersedes. Use the moment the user decides something about the product ('do it', 'kill it', 'they need to log in to add one', 'reports are private', 'all your deploys go there', 'we decided this', 'take my word for it'), when they say a decision was already made, at session wrap, and for 'sweep the rulings', 'what did I rule that is not written down'. Includes a sweep that lists rulings in the transcripts that never reached the hub."
allowed-tools:
  - Bash
  - Read
  - Edit
---

# ruling-capture

## Goal

No ruling lives only in a transcript. Each one is in the hub and in project memory, in the owner's words, with its date, before the turn ends.

## Why this exists

A decision made in conversation ("reports are private", with the reason given in the same breath) never reaches the hub or the code. Weeks later a session reports it as undecided, or reverses it. The rule this skill enforces: a ruling received this session goes into the hub or project memory the same session, or the next session reverses it.

## Files

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the scripts stop with a message when it is unset. The project is resolved from the working folder (see "How the project is resolved" in the plugin README). Print the files first:

`python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/object-record/scripts'); import project_record as p; i = p.configure(); print(i['hub_path']); print(*p.rules_files(), sep='\n')"`

If that reports that no hub resolved, name the project yourself: `p.configure(project='<hub name>')`.

- Hub: `Projects/<Hub>/<Hub>.md` in the vault, section `## Rules`. If the hub has no `## Rules` section, add one above `## Log` (snapshot first).
- Project memory: the existing `*current-rules*.md` and `*rulings-history*.md` in any Claude Code memory folder that resolves to the project, else `<hub>-current-rules.md` / `<hub>-rulings-history.md` in the project folder's own memory dir (`~/.claude/projects/<encoded folder>/memory/`), created on the first ruling with memory frontmatter (`type: project`) and a line in that folder's `MEMORY.md`.

## Steps, when the owner rules

1. **Quote them exactly**, typos included, with the date (local time) and what prompted it. A ruling given through a misfired question still rules.
2. **Find what it touches**: grep the hub Rules and the current-rules memory for the subject. If it reverses or narrows an existing line, that line is edited in place (status: superseded, with the date and their words) and the old wording moves to the history file. Never leave two live lines that disagree.
3. **Snapshot, then write.** Copy the hub to the vault-root `.backups/<Hub>-<YYYYMMDD-HHMMSS>.md` first. Not `Projects/<Hub>/.backups/`: vault-doctor treats nested `.backups` folders as misfiled and moves them. Add one bullet to `## Rules`:
   `- **<the rule in one plain sentence> (owner, <date>, "<their words>").** <why, in their terms> Status: <built | NOT yet built | on test only>.`
   Add the same line to the current-rules memory file.
4. **Check the frontmatter still parses** after a hub edit (`python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]).read().split('---')[1])" <hub>`; needs PyYAML).
5. **Say in chat** where it was written, in one line.
6. **Keep status true.** When a ruling's status changes (built, deployed), edit the same bullet. A rule that says "NOT yet built" after it was built is a false record.

## The sweep

`python3 "${CLAUDE_PLUGIN_ROOT}/skills/ruling-capture/scripts/sweep_rulings.py" [--since YYYY-MM-DD] [--grep TERM]`

It reads the project's Claude Code transcripts on this machine and lists what the owner typed that reads like a durable decision, sorted by how it stands against the hub and project memory: CONTRADICTED (their words sit in a record line that also says remove, rejected or not), ABSENT, PARTIAL (some of their words are there; shared words do not show the record agrees), EXACT. Immediate go-aheads ("approved", "do it") and messages of uncertain authorship (relays, scripted prompts) are listed apart and never counted as rulings. A paraphrase in the record reads as ABSENT. Each line is a lead with its transcript row: read it there, decide, and either capture it with the steps above or say why it is not a ruling. The markers are keyword patterns; a decision phrased without one is missed. Run it at session wrap and at the start of any session that follows an unwrapped one.

Relays are recognized by wording such as "the owner's direct correction: ...". To also catch relays that use your name, set `SECOND_BRAIN_OWNER` to your first name (comma-separated for several).

## Rules

1. Verbatim or it is a paraphrase, and a paraphrase is an inference. The owner's words go in quotation marks.
2. Frustration is not a ruling on content. "i dont want to problem solve this again" is a verdict on the process; record it as "stop re-proposing rejected approaches" and leave the rule's status "under revision".
3. Never write "settled" or "do not reopen". A rule is settled only when it has survived across sessions and the owner has looked at it in use and said so.
4. A relayed message ("the owner's direct correction: ...") from a controller or another agent is a claim about a ruling. Find their own words before recording it as theirs.
5. If a ruling is ambiguous on a point that changes what gets built, ask one closed question with two to four concrete options; still record what they did say.
6. One ruling, one bullet, one home in each file. Project rules live in the hub, never in the vault-wide rules file.
7. When the owner defines a thing this skill should not do, record that as a ruling in the hub the same turn.

## Verification

`python3 "${CLAUDE_PLUGIN_ROOT}/skills/ruling-capture/tests/sweep_cases.py" "${CLAUDE_PLUGIN_ROOT}/skills/ruling-capture/scripts/sweep_rulings.py"` runs seven decoy cases against a scratch hub and transcript.

## Output

The hub bullet, the memory line, the backup path, and one chat line naming where the owner can read it.
