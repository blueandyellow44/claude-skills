#!/usr/bin/env python3
"""
vault-vitals.py - deterministic health monitor for a markdown vault.

Measures the drift metrics that catch the recurring failure modes:
  - orphans            : in-graph notes with zero inbound wikilinks
  - dead_links         : wikilink targets that do not resolve (../ links included)
  - dotdot_links       : wikilinks using filesystem-relative paths (Obsidian phantoms)
  - frontmatter_gaps   : notes missing frontmatter or a status field
  - pipeline freshness : days since each capture pipeline last received a file
  - daily freshness    : days since the newest Daily/YYYY-MM-DD.md

No third-party dependencies. Safe to run nightly. Appends one dated row to a
markdown trend log so weekly digests can read history.

Usage:
  python3 vault-vitals.py [--vault PATH] [--log PATH] [--append] [--json]

The vault is --vault, else the SECOND_BRAIN_VAULT environment variable; with
neither the script stops. Default log: <vault>/Resources/operator/vitals.md.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone

# Directories never scanned. .transcripts holds graph-excluded raw transcripts.
# .backups added 2026-08-18: the snapshots taken before canonical edits were being
# counted as curated notes, inflating every metric a little more per session —
# the "worsening trend" was substantially backup accumulation. Backups are
# recovery artifacts, not notes; vault-audit's misfiled_backups check now
# flags any backup file living outside the root .backups/.
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "dist",
             "build", "__pycache__", ".transcripts", ".backups"}

# Capture pipelines to watch for freshness, as {label: vault-relative root}.
# Empty by default: a vault with no capture automation has nothing to watch,
# and guessing at folders would flag ones its owner never asked for. Add yours,
# for example {"Cowork-Sessions": "Intelligence/Cowork-Sessions"}.
PIPELINES = {}

STALE_DAYS = 7  # default: a pipeline quiet longer than this is flagged

# Per-pipeline freshness bars, keyed to each pipeline's real cadence. A global
# 7 days is too loose for a job that runs daily: it could die and stay "green"
# for almost a week. Example: {"Cowork-Sessions": 3}.
PIPELINE_STALE_DAYS = {}

# Coverage-based staleness. The newest-file freshness rule above only catches a
# TOTAL halt of STALE_DAYS+; it is blind to a backlog, because a few recent
# files mask hundreds of uncaptured sessions. A capture job can write COVERAGE_REL each run with
# how many known sessions are still uncaptured. For coverage-tracked pipelines we
# read it so a growing backlog, OR a capture job that has stopped running at all
# (coverage file missing or stale), is flagged.
COVERAGE_REL = "Resources/operator/capture-coverage.json"
COVERAGE_TRACKED = set()   # labels from PIPELINES whose capture job writes a coverage entry
COVERAGE_STALE_DAYS = 2    # coverage older than this => capture job not running
COVERAGE_BACKLOG_MAX = 40  # more uncaptured sessions than this => pipeline behind

# The session-capture layer: machine-generated archives that are intentionally
# loose. They are measured for freshness only, never for orphans, dead links,
# or frontmatter, because holding auto-captured transcripts to curated-note
# conventions produces thousands of meaningless findings and buries real drift.
# Journal/ is treated the same way: dated, machine-written entries with no
# inbound link by design.
SESSION_LAYER_PREFIXES = (
    "Intelligence/Claude-Chats/",
    "Intelligence/Cowork-Sessions/",
    "Intelligence/Claude-Code-Projects/",
    "Resources/sessions/",
    "Journal/",
)


def is_session_layer(relpath):
    rp = relpath.replace("\\", "/")
    return any(rp.startswith(pre) for pre in SESSION_LAYER_PREFIXES)

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def strip_code(text):
    """Remove fenced and inline code so wikilink examples inside backticks
    are not counted as real links (Obsidian does not parse them either)."""
    text = FENCE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def find_md_files(vault):
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return out


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def frontmatter(text):
    """Return the frontmatter block string, or None if absent."""
    s = text.lstrip("﻿").lstrip()
    if not s.startswith("---"):
        return None
    end = s.find("\n---", 3)
    if end == -1:
        return None
    return s[3:end]


def newest_date_in_dir(root):
    """Return (newest_date, age_days, count) for .md files under root.
    Date is parsed from the filename's leading YYYY-MM-DD when present,
    else the file mtime. Returns (None, None, 0) if the dir is empty/missing."""
    if not os.path.isdir(root):
        return None, None, 0
    newest = None
    count = 0
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            count += 1
            m = DATE_RE.match(f)
            if m:
                try:
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    d = None
            else:
                d = None
            if d is None:
                try:
                    d = datetime.fromtimestamp(
                        os.path.getmtime(os.path.join(r, f))).date()
                except OSError:
                    d = None
            if d and (newest is None or d > newest):
                newest = d
    if newest is None:
        return None, None, count
    age = (date.today() - newest).days
    return newest, age, count


def read_capture_coverage(vault):
    """Read the capture-coverage JSON the backfill job writes each run.
    Returns (data_or_None, age_days_or_None). age_days is days since the file's
    `checked_at` date, falling back to file mtime."""
    path = os.path.join(vault, COVERAGE_REL)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None, None
    d = None
    checked = data.get("checked_at")
    if isinstance(checked, str):
        m = DATE_RE.match(checked)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                d = None
    if d is None:
        try:
            d = datetime.fromtimestamp(os.path.getmtime(path)).date()
        except OSError:
            d = None
    age = (date.today() - d).days if d is not None else None
    return data, age


def coverage_verdict(coverage, cov_age, pipeline_name):
    """(is_stale, reason) for a coverage-tracked capture pipeline. A pipeline is
    flagged when there is no coverage file (capture job never ran), the coverage
    has gone stale (capture job stopped running), there is no entry for it, or the
    uncaptured backlog exceeds the ceiling. (False, None) means coverage is healthy."""
    if coverage is None:
        return True, "no capture-coverage file (capture job has not run)"
    if cov_age is not None and cov_age > COVERAGE_STALE_DAYS:
        return True, f"coverage {cov_age}d stale (capture job not running)"
    entry = (coverage.get("pipelines") or {}).get(pipeline_name)
    if not isinstance(entry, dict):
        return True, "no coverage entry for this pipeline"
    uncaptured = entry.get("uncaptured")
    if isinstance(uncaptured, int) and uncaptured > COVERAGE_BACKLOG_MAX:
        return True, f"{uncaptured} sessions uncaptured"
    return False, None


def resolve_vault(arg=None):
    """--vault wins, then the SECOND_BRAIN_VAULT environment variable. Never guessed."""
    v = arg or os.environ.get("SECOND_BRAIN_VAULT")
    if not v:
        sys.exit("SECOND_BRAIN_VAULT is not set and no --vault was given. Set it to the "
                 "absolute path of your vault (see the plugin README).")
    v = os.path.abspath(os.path.expanduser(v))
    if not os.path.isdir(v):
        sys.exit("vault not found: %s (check SECOND_BRAIN_VAULT or --vault)" % v)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None,
                    help="vault root; default: the SECOND_BRAIN_VAULT environment variable")
    ap.add_argument("--log", default=None)
    ap.add_argument("--append", action="store_true",
                    help="append/update today's row in the trend log")
    ap.add_argument("--json", action="store_true",
                    help="emit metrics as JSON instead of text")
    args = ap.parse_args()

    vault = resolve_vault(args.vault)

    files = find_md_files(vault)
    if not files:
        print(f"ERROR: no markdown files under {vault}", file=sys.stderr)
        return 2

    relpaths = []
    contents = {}
    basename_map = {}   # lower basename (no ext) -> set of relpaths
    relpath_map = {}    # lower relpath (no ext) -> relpath
    ignored = set()     # relpaths tagged obsidian/ignore (graph-excluded)

    for p in files:
        r = os.path.relpath(p, vault)
        relpaths.append(r)
        text = read_text(p)
        contents[r] = text
        fm = frontmatter(text)
        if fm and "obsidian/ignore" in fm:
            ignored.add(r)
        base = os.path.splitext(os.path.basename(r))[0].lower()
        basename_map.setdefault(base, set()).add(r)
        rp = os.path.splitext(r)[0].lower().replace("\\", "/")
        relpath_map[rp] = r

    def resolve(target):
        """Resolve a wikilink target to a relpath, or None if it does not
        resolve. ../ and ./ prefixed targets never resolve (Obsidian reality)."""
        t = target.split("|")[0].split("#")[0].strip()
        if not t or t.startswith("#"):
            return None
        if t.startswith(("http://", "https://")):
            return None
        if t.startswith(".") or "/../" in t:  # ../ ./ ../../ -> phantom
            return None
        tn = t.lower().replace("\\", "/")
        if tn.endswith(".md"):
            tn = tn[:-3]
        if "/" in tn:
            hit = relpath_map.get(tn)
            if hit:
                return hit
            # Obsidian resolves a partial path by suffix match, e.g.
            # [[Alpha/sessions]] -> Projects/Alpha/sessions.md. Mirror that:
            # any relpath whose tail equals the target resolves. Deterministic
            # pick (sorted) when more than one tail matches.
            cands = [rp for key, rp in relpath_map.items()
                     if key == tn or key.endswith("/" + tn)]
            return sorted(cands)[0] if cands else None
        s = basename_map.get(tn)
        # Deterministic pick for ambiguous basenames (e.g. several sessions.md):
        # sorted() is stable across processes; next(iter(set)) is not, because
        # Python randomizes string-set iteration order per run.
        return sorted(s)[0] if s else None

    # Inbound links are counted from EVERY file (a chat transcript linking
    # [[Alpha]] legitimately connects Alpha), but dead-link and ../-link
    # findings are only reported when the SOURCE is a curated file. Noise from
    # the session layer is excluded from the headline metrics.
    inbound = {r: 0 for r in relpaths}
    dead_links = []
    dotdot_links = []

    for r in relpaths:
        body = strip_code(contents[r])
        curated_src = not is_session_layer(r) and r not in ignored
        for m in WIKILINK_RE.finditer(body):
            raw = m.group(1)
            target_only = raw.split("|")[0].split("#")[0].strip()
            if target_only.startswith(("../", "./")):
                if curated_src:
                    dotdot_links.append((r, raw))
            if target_only.startswith("#") or target_only.startswith(("http://", "https://")):
                continue
            resolved = resolve(raw)
            if resolved is None:
                if curated_src:
                    dead_links.append((r, raw))
            elif resolved != r:
                inbound[resolved] += 1

    def is_structural(r):
        base = os.path.basename(r).lower()
        if base in ("claude.md", "readme.md", "index.md"):
            return True
        if base.endswith(".calendar.md"):
            return True
        low = r.lower()
        rp = r.replace("\\", "/")
        if "/templates/" in low or base.startswith("_"):
            return True
        # Dated capture leaves: daily logs, captured sources, unprocessed inbox.
        # No inbound link is expected (you link FROM them, not TO them), so a
        # missing inbound is never an actionable orphan. Journal/ is covered by
        # the session layer. Still measured for dead links and frontmatter.
        if rp.startswith(("Daily/", "Intelligence/Sources/", "_inbox/")):
            return True
        # Frozen archives: completed/superseded bundles moved under
        # Intelligence/archive/. They are historical
        # snapshots, not the curated working layer, and are not expected to
        # carry inbound links. Still measured for dead links and frontmatter.
        if rp.startswith("Intelligence/archive/"):
            return True
        # Operator run-output: dated reports the nightly sensors write
        # (daily snapshots and the like). Automation artifacts, not
        # knowledge notes, so a missing inbound is never an actionable orphan.
        if rp.startswith("Resources/operator/reports/"):
            return True
        # Skill machinery and staging: source files and run-output artifacts,
        # not knowledge notes. Never navigated to via wikilink.
        if base in ("skill.md", "install.md", "change-tracker.md"):
            return True
        if "/examples/" in low or "/_staging/" in low:
            return True
        # Retired skills and agent definitions are machinery too (root
        # CLAUDE.md rule #2 exempts "skill machinery" wholesale; _retired/
        # and _agents/ were missing here — aligned 2026-08-18). Their
        # references/ and evals/ subfolders ride along.
        if rp.startswith(("Skills/_retired/", "Skills/_agents/")):
            return True
        if rp.startswith("Skills/") and ("/references/" in low or "/evals/" in low or "/.tmp/" in low):
            return True
        fm = frontmatter(contents[r]) or ""
        if re.search(r"^\s*type:\s*index\b", fm, re.MULTILINE):
            return True
        return False

    # Headline orphans: curated layer only. Session-layer orphans are tracked
    # separately as an FYI (they signal the backfill auto-linker, not vault rot).
    orphans = [r for r in relpaths
               if inbound[r] == 0 and r not in ignored
               and not is_session_layer(r) and not is_structural(r)]
    session_orphans = [r for r in relpaths
                       if inbound[r] == 0 and r not in ignored
                       and is_session_layer(r) and not is_structural(r)]

    def needs_status(r):
        base = os.path.basename(r).lower()
        if base in ("claude.md", "readme.md") or base.endswith(".calendar.md"):
            return False
        if "/templates/" in r.lower() or base.startswith("_"):
            return False
        return True

    # Frontmatter gaps: curated layer only. Session-capture artifacts are
    # exempt from the status-field convention.
    frontmatter_gaps = []
    for r in relpaths:
        if r in ignored or is_session_layer(r) or not needs_status(r):
            continue
        fm = frontmatter(contents[r])
        if fm is None or not re.search(r"^\s*status:\s*\S", fm, re.MULTILINE):
            frontmatter_gaps.append(r)

    coverage, cov_age = read_capture_coverage(vault)
    pipelines = {}
    for name, rel in PIPELINES.items():
        newest, age, count = newest_date_in_dir(os.path.join(vault, rel))
        bar = PIPELINE_STALE_DAYS.get(name, STALE_DAYS)
        age_stale = (age is not None and age > bar)
        cov_stale, cov_reason = (False, None)
        if name in COVERAGE_TRACKED:
            cov_stale, cov_reason = coverage_verdict(coverage, cov_age, name)
        pipelines[name] = {
            "newest": newest.isoformat() if newest else None,
            "age_days": age,
            "count": count,
            "stale": age_stale or cov_stale,
            "empty": (count == 0),
            "coverage_reason": cov_reason,
        }

    dn, dage, _ = newest_date_in_dir(os.path.join(vault, "Daily"))

    today = date.today().isoformat()
    in_scope = len([r for r in relpaths if r not in ignored])
    curated_files = len([r for r in relpaths
                         if r not in ignored and not is_session_layer(r)])
    metrics = {
        "date": today,
        "files_in_graph": in_scope,
        "files_total": len(relpaths),
        "curated_files": curated_files,
        "orphans": len(orphans),
        "dead_links": len(dead_links),
        "dotdot_links": len(dotdot_links),
        "frontmatter_gaps": len(frontmatter_gaps),
        "session_orphans": len(session_orphans),
        "daily_age_days": dage,
        "pipelines": pipelines,
    }

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Vault vitals - {today}  ({vault})")
        print(f"  curated notes      : {curated_files}  (total .md {len(relpaths)})")
        print("  -- curated-layer health (these should trend to ~0) --")
        print(f"  orphans            : {len(orphans)}")
        print(f"  dead wikilinks     : {len(dead_links)}")
        print(f"  ../ path links     : {len(dotdot_links)}")
        print(f"  frontmatter gaps   : {len(frontmatter_gaps)}")
        print(f"  daily age (days)   : {dage}")
        print(f"  session-layer orphans (FYI, backfill auto-linker): {len(session_orphans)}")
        print("  pipelines:")
        for name, info in pipelines.items():
            flag = " STALE" if info["stale"] else (" EMPTY" if info["empty"] else "")
            reason = f"  [{info['coverage_reason']}]" if info.get("coverage_reason") else ""
            print(f"    {name:22s} newest {info['newest']}  age {info['age_days']}  files {info['count']}{flag}{reason}")
        if orphans:
            print(f"  orphan sample ({min(len(orphans),15)} of {len(orphans)}):")
            for r in sorted(orphans):
                print(f"    - {r}")
        if dotdot_links:
            print(f"  ../ link sample ({min(len(dotdot_links),15)} of {len(dotdot_links)}):")
            for r, raw in dotdot_links[:15]:
                print(f"    - {r}: [[{raw}]]")
        # one-line machine-readable summary for schedulers
        stale = [n for n, i in pipelines.items() if i["stale"] or i["empty"]]
        print("VITALS " + " ".join([
            today,
            f"files={in_scope}",
            f"orphans={len(orphans)}",
            f"dead={len(dead_links)}",
            f"dotdot={len(dotdot_links)}",
            f"fmgaps={len(frontmatter_gaps)}",
            f"daily_age={dage}",
            f"stale_pipelines={','.join(stale) if stale else 'none'}",
        ]))

    if args.append:
        log = args.log or os.path.join(vault, "Resources", "operator", "vitals.md")
        write_log(log, metrics)
        print(f"\nappended to {log}")

    return 0


def write_log(log_path, m):
    """Create the trend log if missing, then upsert today's row (newest first)."""
    header_fm = (
        "---\n"
        "title: Vault vitals log\n"
        "type: index\n"
        "status: active\n"
        "tags: [operator, vitals, health]\n"
        f"updated: {m['date']}\n"
        "---\n\n"
        "Deterministic nightly health snapshot written by `vault-vitals.py`. "
        "One row per run, newest first. A smoke detector, not the deep clean: "
        "if a number climbs, run the vault-groom skill.\n\n"
        "Columns track the curated layer (notes meant to follow vault conventions). "
        "The session-capture layer is measured for freshness only, in the stale-pipelines column.\n\n"
        "## Trend\n\n"
        "| date | curated notes | orphans | dead links | ../ links | frontmatter gaps | daily age | stale pipelines |\n"
        "|------|------:|--------:|-----------:|----------:|-----------------:|----------:|-----------------|\n"
    )
    stale = [n for n, i in m["pipelines"].items() if i["stale"] or i["empty"]]
    row = (
        f"| {m['date']} | {m['curated_files']} | {m['orphans']} | "
        f"{m['dead_links']} | {m['dotdot_links']} | {m['frontmatter_gaps']} | "
        f"{m['daily_age_days']} | {','.join(stale) if stale else 'none'} |"
    )

    existing_rows = []
    if os.path.isfile(log_path):
        old = read_text(log_path)
        for line in old.splitlines():
            s = line.strip()
            if re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", s):
                row_date = s.split("|")[1].strip()
                if row_date != m["date"]:
                    existing_rows.append(s)

    rows = [row] + existing_rows  # newest first
    rows.sort(key=lambda x: x.split("|")[1].strip(), reverse=True)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(header_fm)
        fh.write("\n".join(rows) + "\n")


if __name__ == "__main__":
    sys.exit(main())
