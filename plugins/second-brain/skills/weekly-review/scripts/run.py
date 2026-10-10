#!/usr/bin/env python3
"""
weekly-review: scan the vault for this week's activity and write a review file.

Usage:
  run.py                    # current ISO week, write to file
  run.py --week 2026-W18    # specific ISO week
  run.py --dry-run          # render to stdout, do not write file

Output:
  <vault>/Resources/Reviews/YYYY-W##.md (idempotent within a week)
  The vault is the SECOND_BRAIN_VAULT environment variable.

Exit codes:
  0 = success
  1 = bad arguments
  2 = SECOND_BRAIN_VAULT unset, or vault not found
"""

import argparse
import datetime
import glob
import os
import re
import sys
from pathlib import Path

# ---------- vault location ----------

def resolve_vault():
    """Resolve the vault path from SECOND_BRAIN_VAULT. Never guessed."""
    env_path = os.environ.get('SECOND_BRAIN_VAULT')
    if not env_path:
        print('ERROR: SECOND_BRAIN_VAULT is not set. Set it to the absolute path of your vault '
              '(see the plugin README).', file=sys.stderr)
        sys.exit(2)
    p = Path(env_path).expanduser().resolve()
    if not p.is_dir():
        print(f'ERROR: vault not found at {p}', file=sys.stderr)
        sys.exit(2)
    return p


# ---------- ISO week math ----------

def iso_week_range(year, week):
    """Return (Monday, Sunday) date objects for ISO week (year, week)."""
    monday = datetime.date.fromisocalendar(year, week, 1)
    sunday = datetime.date.fromisocalendar(year, week, 7)
    return monday, sunday


def parse_iso_week(s):
    """Parse 'YYYY-W##' into (year, week). Raises ValueError on bad input."""
    m = re.match(r'^(\d{4})-W(\d{1,2})$', s)
    if not m:
        raise ValueError(f"Bad week format: {s!r}. Expected YYYY-W##.")
    year, week = int(m.group(1)), int(m.group(2))
    # Validate week number is real for that year
    try:
        datetime.date.fromisocalendar(year, week, 1)
    except ValueError as e:
        raise ValueError(f"Invalid ISO week {year}-W{week:02d}: {e}")
    return year, week


def current_iso_week(today=None):
    today = today or datetime.date.today()
    iso = today.isocalendar()
    return iso[0], iso[1]


def previous_iso_week(year, week):
    """Compute the ISO week before (year, week). Handles year boundary."""
    if week > 1:
        return year, week - 1
    # week == 1, previous is last week of (year - 1), could be 52 or 53.
    try:
        datetime.date.fromisocalendar(year - 1, 53, 1)
        return year - 1, 53
    except ValueError:
        return year - 1, 52


# ---------- scanners ----------

def scan_lessons(vault, start, end):
    """Find lesson entries in Tasks/lessons.md dated in [start, end].

    Supports two formats (current and legacy):
    1. CURRENT: `## YYYY-MM-DD` H2 headers with `### [Project] Rule: <headline>`
       H3 entries underneath; the `[Project]` tag is optional (`### Rule: ...`,
       the form the vault-setup templates teach, is listed as "general"). Body
       is the prose between the H3 and the next H3 or H2.
    2. LEGACY: `- [YYYY-MM-DD] [Project] Rule: <body>` flat bullets.

    Both forms are extracted; ordered by date.
    """
    path = vault / 'Tasks' / 'lessons.md'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    entries = []

    # Format 1: H2 date sections with H3 entries
    h2_pattern = re.compile(
        r'^## (\d{4}-\d{2}-\d{2})\n(.+?)(?=\n## |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    h3_pattern = re.compile(
        r'^### (?:\[([^\]]+)\] )?Rule: ([^\n]+)\n+(.*?)(?=\n### |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    for h2 in h2_pattern.finditer(text):
        date_str = h2.group(1)
        try:
            d = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        section = h2.group(2)
        for h3 in h3_pattern.finditer(section):
            project = h3.group(1) or 'general'
            headline = h3.group(2).strip()
            body = h3.group(3).strip()
            # Headline is already a sentence. Use it as the summary.
            # If body is empty, headline alone; else include first body sentence.
            summary = headline
            if not summary.endswith('.'):
                summary += '.'
            entries.append({'date': date_str, 'project': project, 'summary': summary})

    # Format 2: legacy bullet form
    legacy_pattern = re.compile(
        r'^- \[(\d{4}-\d{2}-\d{2})\] \[([^\]]+)\] Rule: (.+?)(?=\n- \[\d{4}-\d{2}-\d{2}\]|\n## |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    for m in legacy_pattern.finditer(text):
        date_str = m.group(1)
        try:
            d = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        project = m.group(2)
        body = m.group(3).strip()
        first_period = body.find('. ')
        if 0 < first_period < 240:
            summary = body[:first_period + 1]
        else:
            summary = body[:240].rstrip()
            if len(body) > 240:
                summary += '...'
        entries.append({'date': date_str, 'project': project, 'summary': summary})

    # Sort by date, then preserve insertion order within a date
    entries.sort(key=lambda e: e['date'])
    return entries


def scan_roe(vault, start, end):
    """Find ROE entries with the most recent date pointer in [start, end]."""
    path = vault / 'Rules-of-Engagement.md'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    entries = []
    for line in text.splitlines():
        # Only consider bulleted lines that look like rules.
        if not line.startswith('- **'):
            continue
        # Find all YYYY-MM-DD dates anywhere on the line.
        date_strs = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', line)
        if not date_strs:
            continue
        dates = []
        for ds in date_strs:
            try:
                dates.append(datetime.date.fromisoformat(ds))
            except ValueError:
                pass
        if not dates:
            continue
        most_recent = max(dates)
        if not (start <= most_recent <= end):
            continue
        # Extract the bolded headline as the rule label.
        m = re.match(r'^- \*\*(.+?)\*\*', line)
        if m:
            rule = m.group(1).rstrip('.')
        else:
            rule = line[2:].strip()[:200]
        entries.append({'date': most_recent.isoformat(), 'rule': rule})
    return entries


def scan_daily(vault, start, end):
    """List Daily/<date>.md files in range with non-trivial content."""
    out = []
    cur = start
    while cur <= end:
        path = vault / 'Daily' / f'{cur.isoformat()}.md'
        # Skip empty stubs (a template-sized daily file is a couple of hundred bytes)
        if path.exists() and path.stat().st_size > 300:
            out.append(cur.isoformat())
        cur += datetime.timedelta(days=1)
    return out


def scan_sessions(vault, start, end):
    """List Cowork session files dated in range."""
    pattern = str(vault / 'Intelligence' / 'Cowork-Sessions' / '????-??-?? *.md')
    matches = sorted(glob.glob(pattern))
    out = []
    for filepath in matches:
        name = os.path.basename(filepath)
        m = re.match(r'^(\d{4}-\d{2}-\d{2}) (.+)\.md$', name)
        if not m:
            continue
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if start <= d <= end:
            out.append({'date': m.group(1), 'slug': m.group(2), 'filename': name[:-3]})
    return out


def scan_sources(vault, start, end):
    """List Intelligence/Sources files dated in range."""
    pattern = str(vault / 'Intelligence' / 'Sources' / '????-??-?? *.md')
    matches = sorted(glob.glob(pattern))
    out = []
    for filepath in matches:
        name = os.path.basename(filepath)
        m = re.match(r'^(\d{4}-\d{2}-\d{2}) (.+)\.md$', name)
        if not m:
            continue
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if start <= d <= end:
            out.append({'date': m.group(1), 'title': m.group(2), 'filename': name[:-3]})
    return out


def latest_open_loops(vault):
    """Pull the most recent **Still open** bulletlist from Tasks/todo.md."""
    path = vault / 'Tasks' / 'todo.md'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    # Find every "**Still open**" section, take the LAST one.
    pattern = re.compile(
        r'\*\*Still open\*\*:?\s*\n((?:    -[^\n]*\n?)+)',
    )
    matches = pattern.findall(text)
    if not matches:
        return []
    last = matches[-1]
    items = re.findall(r'^    -\s*(.+)$', last, re.MULTILINE)
    # Keep the bullet text as-is (Markdown-formatted, which renders fine in the review).
    return items


def answer_in_file(path):
    """Extract the calibration answer from a review file at `path`.

    Return value:
      None  = no file, or no calibration block found.
      ''    = block present but the answer slot is empty/whitespace.
      <str> = the answer text as written.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    # Everything after "Answer:" until the next H2 or HR or EOF.
    m = re.search(
        r'\*\*Did the vault help me find or write or decide anything this week\?\*\*\s*\n\s*\n'
        r'Answer:\s*\n(.*?)(?=\n##\s|\n---\s|\Z)',
        text,
        re.DOTALL,
    )
    if not m:
        return None
    return m.group(1).strip()


def previous_week_answer(vault, year, week):
    """Calibration answer from the PREVIOUS week's file (drives the empty-streak warning)."""
    prev_year, prev_week = previous_iso_week(year, week)
    return answer_in_file(vault / 'Resources' / 'Reviews' / f'{prev_year}-W{prev_week:02d}.md')


def existing_answer(out_path):
    """Calibration answer already written in THIS week's file, so a re-render
    never destroys it (an earlier render always emitted a blank `Answer:`,
    so re-running the same week, including a scheduled run, erased the
    one field the file exists to collect)."""
    return answer_in_file(out_path)


# ---------- renderer ----------

def render_review(year, week, lessons, roe, daily, sessions, sources, open_loops, prev_answer, kept_answer=None):
    monday, sunday = iso_week_range(year, week)
    week_label = f'{year}-W{week:02d}'
    today = datetime.date.today().isoformat()

    L = []
    L.append('---')
    L.append(f'title: Weekly Review {week_label}')
    L.append('type: review')
    L.append(f'iso_week: {week_label}')
    L.append(f'week_start: {monday.isoformat()}')
    L.append(f'week_end: {sunday.isoformat()}')
    L.append(f'generated: {today}')
    L.append('---')
    L.append('')
    L.append(f'# Weekly Review {week_label}')
    L.append('')
    L.append(f'Part of [[Reviews]]. Week of {monday.strftime("%b %d")} to {sunday.strftime("%b %d, %Y")}.')
    L.append('')

    # Trend banner (above the calibration question, so the owner sees it first)
    if prev_answer == '':
        L.append('> [!warning] Last week\'s calibration question was unanswered.')
        L.append('> If this week\'s answer also stays empty, the vault is not earning its keep this period.')
        L.append('')
    elif prev_answer is None:
        L.append('> [!info] No prior review file found. Trend tracking starts this week.')
        L.append('')

    # Calibration FIRST
    L.append('## Calibration')
    L.append('')
    L.append('**Did the vault help me find or write or decide anything this week?**')
    L.append('')
    if kept_answer:
        L.append('Answer:')
        L.append(kept_answer)
        L.append('')
    else:
        L.append('Answer:')
        L.append('')
        L.append('')

    # New lessons
    L.append('## New lessons logged')
    L.append('')
    if lessons:
        for entry in lessons:
            L.append(f'- **{entry["date"]}** [{entry["project"]}]: {entry["summary"]}')
    else:
        L.append('(none this week)')
    L.append('')

    # New ROE entries
    L.append('## ROE entries dated this week')
    L.append('')
    if roe:
        for entry in roe:
            L.append(f'- **{entry["date"]}**: {entry["rule"]}')
    else:
        L.append('(none this week)')
    L.append('')

    # Daily entries
    L.append('## Daily entries')
    L.append('')
    if daily:
        for d in daily:
            L.append(f'- [[{d}]]')
    else:
        L.append('(no daily entries this week)')
    L.append('')

    # Cowork sessions
    L.append('## Cowork sessions')
    L.append('')
    if sessions:
        for s in sessions:
            L.append(f'- **{s["date"]}**: [[{s["filename"]}|{s["slug"]}]]')
    else:
        L.append('(no Cowork sessions this week)')
    L.append('')

    # Captured sources
    L.append('## Captured sources')
    L.append('')
    if sources:
        for src in sources:
            L.append(f'- **{src["date"]}**: [[{src["filename"]}|{src["title"]}]]')
    else:
        L.append('(no sources captured this week)')
    L.append('')

    # Open loops snapshot
    L.append('## Open loops (snapshot from `Tasks/todo.md`)')
    L.append('')
    if open_loops:
        for item in open_loops[:20]:
            L.append(f'- {item}')
    else:
        L.append('(no open loops found in the most recent Session review)')
    L.append('')

    return '\n'.join(L)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description='Generate a weekly review file from vault activity.')
    ap.add_argument('--week', help='ISO week as YYYY-W## (default: current week)')
    ap.add_argument('--dry-run', action='store_true', help='Render to stdout, do not write file')
    args = ap.parse_args()

    vault = resolve_vault()

    try:
        if args.week:
            year, week = parse_iso_week(args.week)
        else:
            year, week = current_iso_week()
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    monday, sunday = iso_week_range(year, week)

    lessons = scan_lessons(vault, monday, sunday)
    roe = scan_roe(vault, monday, sunday)
    daily = scan_daily(vault, monday, sunday)
    sessions = scan_sessions(vault, monday, sunday)
    sources = scan_sources(vault, monday, sunday)
    open_loops = latest_open_loops(vault)
    prev_answer = previous_week_answer(vault, year, week)

    out_path = vault / 'Resources' / 'Reviews' / f'{year}-W{week:02d}.md'
    kept_answer = existing_answer(out_path)

    review = render_review(year, week, lessons, roe, daily, sessions, sources, open_loops,
                           prev_answer, kept_answer)

    if args.dry_run:
        print(review)
        print(f'\n# DRY RUN. Would write to: {out_path}', file=sys.stderr)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(review, encoding='utf-8')

    print(f'Wrote: {out_path}')
    print(
        f'Sections populated: lessons={len(lessons)} roe={len(roe)} '
        f'daily={len(daily)} sessions={len(sessions)} sources={len(sources)} '
        f'open_loops={len(open_loops)}'
    )
    if prev_answer == '':
        print('FLAG: previous week calibration was unanswered. Two-weeks-running risk if this week stays empty.')
    elif prev_answer is None:
        print('NOTE: no previous week file found. Trend tracking starts this week.')


if __name__ == '__main__':
    main()
