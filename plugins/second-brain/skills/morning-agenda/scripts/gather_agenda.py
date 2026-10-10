#!/usr/bin/env python3
"""
gather_agenda.py — collect static (non-calendar) data for the morning-agenda skill.

Reads:
  - <vault>/Resources/Prompts/session-handoff-*.md  (latest by mtime)
  - <vault>/Tasks/todo.md                            (latest "Still open" block)
  - <vault>/Projects/<Name>/<Name>.md                (active project hubs)

Writes nothing. Outputs JSON to stdout.

Calendar events are NOT fetched here — they come from the MCP at runtime in the
SKILL.md orchestration. This script is the deterministic, no-network half.

Validate at boundaries: every path is checked before reading. Missing or
malformed inputs land in `warnings[]` rather than crashing the run.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2

# Cap any single section so we never flood the agent's context.
MAX_OPEN_ITEMS = 20
MAX_PROJECTS = 12
HANDOFF_GLOB = "session-handoff-*.md"

# Bullet patterns we accept under "Still open" / "Open items":
# - "- foo"
# - "* foo"
# - "1. foo"  (numbered list)
# Bold-prefixed items like "- **Install**: ..." also caught.
BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*\S)\s*$")

# Section headers we look for inside the latest todo.md (case-insensitive).
TODO_OPEN_HEADERS = (
    "still open",
    "open items",
    "still pending",
    "what's still open",
    "what is open",
    "what's open",
    "open loops",
    "open threads",
)


def _safe_read(path: Path) -> str | None:
    """Read a UTF-8 file. Return None on any failure (with a printed warning)."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (PermissionError, OSError, UnicodeDecodeError) as exc:
        print(f"[gather_agenda] WARN: could not read {path}: {exc}", file=sys.stderr)
        return None


def _today_strings(tz_offset_hours: float | None = None) -> tuple[str, str]:
    """Return (iso_date, human_date) for "today" in local time.

    With no offset the machine's own local clock decides. Pass --tz-offset
    (hours from UTC) to pin another zone.
    """
    if tz_offset_hours is None:
        local = _dt.datetime.now()
    else:
        local = _dt.datetime.now(tz=_dt.timezone.utc) + _dt.timedelta(hours=tz_offset_hours)
    iso = local.strftime("%Y-%m-%d")
    human = local.strftime("%A, %B %-d, %Y") if hasattr(local, "strftime") else iso
    return iso, human


def _extract_bullets(block: str, limit: int) -> list[str]:
    """Pull bullet items out of a block of markdown text. Trim to `limit`."""
    out: list[str] = []
    for raw_line in block.splitlines():
        m = BULLET_RE.match(raw_line)
        if not m:
            continue
        text = m.group(1).strip()
        # Strip trailing periods that were just sentence terminators.
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _find_latest_handoff(prompts_dir: Path, warnings: list[str]) -> dict | None:
    """Return latest handoff dict, or None if nothing usable found."""
    if not prompts_dir.is_dir():
        warnings.append(f"Resources/Prompts not found at {prompts_dir}")
        return None

    candidates = sorted(
        (p for p in prompts_dir.glob(HANDOFF_GLOB) if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        warnings.append("No session-handoff-*.md files in Resources/Prompts/")
        return None

    latest = candidates[0]
    vault_root = prompts_dir.parent.parent
    rel_path = _vault_relative(latest, vault_root)

    text = _safe_read(latest)
    if text is None:
        warnings.append(f"Could not read latest handoff: {latest.name}")
        return {"path": rel_path, "title": latest.stem, "open_items": []}

    title = _extract_handoff_title(text) or latest.stem
    open_items = _extract_handoff_open_items(text)
    return {
        "path": rel_path,
        "title": title,
        "open_items": open_items,
    }


def _extract_handoff_title(text: str) -> str | None:
    """First H1 line, falling back to None."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _extract_handoff_open_items(text: str) -> list[str]:
    """
    Pull bullets from the first 'What is open' / 'Open items' / 'Still open'
    section, plus any 'High priority' / 'Medium priority' subsections that
    follow immediately. Stop at the next H2.
    """
    lines = text.splitlines()
    start: int | None = None
    open_section_re = re.compile(
        r"^##\s+(?:what(?:'s|\s+is)?\s+(?:still\s+)?open|open\s+items|still\s+open|still\s+pending|todo|open\s+loops|open\s+threads)\b",
        re.IGNORECASE,
    )
    for idx, line in enumerate(lines):
        if open_section_re.match(line):
            start = idx + 1
            break
    if start is None:
        # Fall back: any "Still open" / "Open items" subsection at H3 too.
        h3_re = re.compile(
            r"^###\s+(?:what(?:'s|\s+is)?\s+(?:still\s+)?open|open\s+items|still\s+open|still\s+pending|open\s+loops|open\s+threads)\b",
            re.IGNORECASE,
        )
        for idx, line in enumerate(lines):
            if h3_re.match(line):
                start = idx + 1
                break
    if start is None:
        return []

    # Walk forward until the next H2 (or H1) or end of file.
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r"^##\s", lines[j]):
            end = j
            break
    block = "\n".join(lines[start:end])
    return _extract_bullets(block, MAX_OPEN_ITEMS)


def _extract_todo_open_items(todo_path: Path, warnings: list[str]) -> list[str]:
    """Extract Still-open items from the LATEST 'Session review' block in todo.md."""
    text = _safe_read(todo_path)
    if text is None:
        warnings.append(f"Tasks/todo.md not found or unreadable at {todo_path}")
        return []

    # Find every "## Session review" header. Take the LAST one.
    review_indices = [
        i for i, line in enumerate(text.splitlines())
        if re.match(r"^##\s+Session review\b", line, re.IGNORECASE)
    ]
    lines = text.splitlines()
    if not review_indices:
        warnings.append("No '## Session review' section found in todo.md")
        # Try anywhere in the file as a fallback.
        return _extract_first_open_block(text)

    last_review_start = review_indices[-1]
    # Block runs to next ## or end of file.
    end = len(lines)
    for j in range(last_review_start + 1, len(lines)):
        if re.match(r"^##\s", lines[j]):
            end = j
            break

    block = "\n".join(lines[last_review_start:end])
    items = _extract_open_within_block(block)
    if not items:
        warnings.append("Latest Session review had no 'Still open' bullets")
    return items


def _extract_first_open_block(text: str) -> list[str]:
    """Anywhere-in-file fallback: find first 'Still open' header and return bullets."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        lower = line.strip().lower()
        if any(h in lower for h in TODO_OPEN_HEADERS) and (
            line.startswith("#") or line.startswith("**") or line.endswith("**:")
        ):
            tail = "\n".join(lines[idx + 1 : idx + 80])
            return _extract_bullets(tail, MAX_OPEN_ITEMS)
    return []


def _normalize_header(line: str) -> str:
    """Strip leading bullet, ** markers, leading/trailing whitespace, trailing colons.

    Used to match a candidate header line against TODO_OPEN_HEADERS. Handles
    every format we have seen in todo.md:
      - "- **Still open**: ..."   -> "still open"
      - "**Still open**:"          -> "still open"
      - "### Still open"           -> "still open"
      - "Still open:"              -> "still open"
    """
    s = line.strip()
    # Strip leading bullet markers (- * + or "1.").
    s = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", s)
    # Strip leading H1-H6 markers.
    s = re.sub(r"^#+\s+", "", s)
    # Drop ALL ** runs anywhere in the line.
    s = s.replace("**", "")
    # Lowercase, strip whitespace, then strip trailing colons + extra whitespace.
    s = s.lower().strip().rstrip(":").strip()
    return s


def _extract_open_within_block(block: str) -> list[str]:
    """
    Within a Session review block, find the 'Still open' subsection and return
    its bullets. The header may be a top-level bullet ("- **Still open**:"),
    bold-only ("**Still open**:"), or H3 ("### Still open").
    """
    lines = block.splitlines()
    for idx, line in enumerate(lines):
        norm = _normalize_header(line)
        # Exact match OR header that ends with one of our target phrases
        # (e.g., "still open from last session").
        if any(norm == h or norm.endswith(" " + h) for h in TODO_OPEN_HEADERS):
            # Greedy: grab the next ~80 lines or until next top-level bold-header bullet.
            tail_lines: list[str] = []
            for follow in lines[idx + 1 :]:
                # Stop at the next top-level (non-indented) bold-header bullet,
                # e.g. "- **Files modified this session**" or "- **Next session**".
                # Indented sub-bullets (which START WITH WHITESPACE) do NOT match.
                if re.match(r"^- \*\*[A-Z][^*]+\*\*", follow):
                    follow_norm = _normalize_header(follow)
                    if not any(follow_norm == h or follow_norm.endswith(" " + h)
                               for h in TODO_OPEN_HEADERS):
                        break
                tail_lines.append(follow)
            return _extract_bullets("\n".join(tail_lines), MAX_OPEN_ITEMS)
    return []


def _list_active_projects(projects_dir: Path, warnings: list[str]) -> list[dict]:
    """List project hubs (folders containing a hub file with the same name)."""
    if not projects_dir.is_dir():
        warnings.append(f"Projects directory not found at {projects_dir}")
        return []

    out: list[dict] = []
    try:
        children = sorted(projects_dir.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        warnings.append(f"Could not list Projects directory: {exc}")
        return []

    for child in children:
        if not child.is_dir():
            continue
        if child.name.startswith((".", "_")):
            continue
        hub_file = child / f"{child.name}.md"
        if not hub_file.is_file():
            continue
        try:
            mtime = hub_file.stat().st_mtime
        except OSError:
            mtime = 0.0
        out.append({
            "name": child.name,
            "hub": _vault_relative(hub_file, projects_dir.parent),
            "_mtime": mtime,
        })
        if len(out) >= MAX_PROJECTS:
            break

    # Sort newest-touched first (proxy for "active").
    out.sort(key=lambda d: d.pop("_mtime", 0.0), reverse=True)
    # Trim again after sort (paranoia).
    return out[:MAX_PROJECTS]


def _vault_relative(path: Path, vault: Path) -> str:
    """Return the path as 'Folder/file.md' relative to vault root, with absolute fallback."""
    try:
        return str(path.relative_to(vault))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect static morning-agenda data for the morning-agenda skill."
    )
    parser.add_argument(
        "--vault",
        default=None,
        help="Absolute path to the vault root. Default: the SECOND_BRAIN_VAULT environment variable.",
    )
    parser.add_argument(
        "--tz-offset",
        type=float,
        default=None,
        help="Hours offset from UTC for the 'today' string. Default: this machine's local time.",
    )
    args = parser.parse_args(argv)

    vault_arg = args.vault or os.environ.get("SECOND_BRAIN_VAULT")
    if not vault_arg:
        print(
            json.dumps(
                {
                    "error": "SECOND_BRAIN_VAULT is not set and no --vault was given. "
                             "Set it to the absolute path of your vault (see the plugin README).",
                },
                indent=2,
            ),
            file=sys.stdout,
        )
        return EXIT_USAGE
    vault = Path(vault_arg).expanduser()
    if not vault.is_dir():
        print(
            json.dumps(
                {
                    "error": f"Vault path is not a directory: {vault}",
                },
                indent=2,
            ),
            file=sys.stdout,
        )
        return EXIT_USAGE

    warnings: list[str] = []
    today_iso, today_human = _today_strings(args.tz_offset)

    handoff = _find_latest_handoff(vault / "Resources" / "Prompts", warnings)
    todo_open = _extract_todo_open_items(vault / "Tasks" / "todo.md", warnings)
    active_projects = _list_active_projects(vault / "Projects", warnings)

    payload = {
        "today_iso": today_iso,
        "today_human": today_human,
        "vault": str(vault),
        "latest_handoff": handoff,
        "todo_open": todo_open,
        "active_projects": active_projects,
        "warnings": warnings,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
