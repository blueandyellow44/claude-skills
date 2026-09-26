# Examples

This folder holds renders the user has approved, so later runs can learn from them.

At the end of an attended run, the skill asks whether to save the output as a good example. On a yes, it writes one file here named `YYYY-MM-DD-HHMM.md` containing:

- The aesthetic or direction and the doc type used.
- The three intent answers (who it is for, what they must accomplish, what it should feel like).
- The input content, or a path to it.
- The rendered HTML, or a path to it.
- The PDF path.
- Any notes on what worked and what to avoid next time.

The skill reads every file in this folder before Step 1. If this README is the only file, that read is skipped.

Keep examples free of anything you would not want reused: private names, client details and credentials do not belong here. If the skill folder is read-only in your install, save examples in your working directory instead and point the skill at them.
