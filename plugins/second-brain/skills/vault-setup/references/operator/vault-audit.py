#!/usr/bin/env python3
# vendored by the vault-setup skill, 2026-08-18, from its own authoring
# vault's operator tooling — genericized for a fresh vault, see below.
"""vault-audit.py — the deterministic detector core of a vault-ops style vault.

Design rules (carried over from the source this was vendored from):
- Deterministic and agent-free: runs whole when the API is shedding load.
- Every finding ships a concrete fix string, never a bare flag.
- Budgets are detectors, not prose: the canon size contract lives HERE.
- A detector is untrusted until seen failing on a known-bad:
  test_vault_audit.py seeds known-bads for every check; run it after any edit.
- Findings the instrument cannot judge get severity "info", never silence.

Genericized for a fresh vault (not the source vault this was vendored from):
- CANON_BUDGETS retuned to a new vault's honest starting sizes, not months
  of accretion. Retune upward as this vault's canon grows.
- PIPELINES starts empty — an empty table is honest for a vault with no
  capture automation yet. Add entries here as scheduled jobs get built.
- is_real_vault() always returns False here (see its docstring) — there is
  no "source vault" this scaffold should ever compare itself against, so the
  machine-specific sub-checks it gates in check_generated_staleness (a
  marketplace lockfile, root-file mirrors, a skills-index builder) stay
  inert by construction rather than by a hardcoded path. The one sub-check
  NOT gated by it — a vault-scoped relay-startup-index staleness check —
  stays active but harmless: it only fires if this vault grows its own
  build-relay-startup-index.py, which vault-setup doesn't create.

Usage:
    python3 vault-audit.py [--vault PATH] [--json] [--only CHECK[,CHECK]]
The vault is --vault, else the SECOND_BRAIN_VAULT environment variable; with
neither the script stops with a message.
Exit: 2 if any FAIL finding, 1 if only WARN, 0 clean (info does not gate).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date

# --- contracts -------------------------------------------------------------

ROOT_FILE_ALLOWLIST = {"CLAUDE.md", "Rules-of-Engagement.md", "AGENTS.md", "runs.json",
                       "Home.md", "Start-here.md"}
ROUTING_EXEMPT_DIRS = {".backups", ".obsidian", ".git", "__pycache__"}

# The Obsidian layer. A vault is something a PERSON opens, not only something a
# session reads: without these, the scaffold is a folder of markdown that
# Obsidian will open as an unconfigured stranger. core-plugins.json is the
# hard requirement (its absence means no vault config at all); the rest each
# disable one thing the owner was promised.
OBSIDIAN_REQUIRED = "core-plugins.json"
OBSIDIAN_EXPECTED = {
    "app.json": "link format, attachment folder, and ignore filters fall back to defaults",
    "appearance.json": "the vault's CSS snippet stays switched off",
    "graph.json": "graph view opens uncoloured and shows orphans",
    "daily-notes.json": "the daily note button writes to the vault root, not Daily/",
    "templates.json": "the template inserter has no folder to read from",
    "workspace.json": "Obsidian opens on an empty pane instead of Home",
}

# Canon size budgets, chars. warn = compress-or-displace tripwire, fail = hard stop.
# Starting sizes for a fresh vault — retune as real canon accrues.
CANON_BUDGETS = {
    "Rules-of-Engagement.md": (8_000, 15_000),
    "CLAUDE.md": (12_000, 20_000),
    "Tasks/todo.md": (50_000, 100_000),
}

# Capture pipelines: path -> (max age days, note). None threshold = watch-only info.
# Empty by design: a freshly scaffolded vault has no capture automation yet, and
# guessing at some would warn about folders its owner never asked for.
#
# Add this vault's pipelines through the per-vault OVERLAY below, not by editing
# this table. Two reasons: the file then stays identical across every vault it is
# vendored into, so it can be re-vendored without losing settings; and anything
# written here ships to every vault, so it must name a mechanism only, never a
# person, a ruling, or a personal project. (The authoring vault learned the second
# one on 2026-08-18, when two owner rulings in this table printed into a foreign
# vault's audit report.)
PIPELINES = {}

# Per-vault overlay, read from the AUDITED vault. Shape:
#   {"<rel path>": {"max_days": <int|null>, "note": "<str>"}}
# A known path overrides field-by-field; an unknown path is added. This is where
# THIS vault's pipelines and its owner's own notes live.
PIPELINES_OVERLAY_REL = "Resources/operator/pipelines.local.json"
AUTOSYNC_MAX_AGE_MIN = 30
INBOX_MAX_AGE_DAYS = 14
VITALS_METRICS = ("orphans", "dead_links", "dotdot_links", "frontmatter_gaps")
VITALS_LOOKBACK_DAYS = 7

# --- canon effectiveness ---------------------------------------------------
#
# The four checks below judge whether the always-loaded canon is still doing
# its job, rather than whether the vault is tidy. They self-seed and stay
# silent on a young vault: canon_flow needs two dated rows before it judges
# anything, and rule_rent and roe_sunset return nothing until the vault has a
# recurrence log and rules old enough to age out. That is the intent. They
# exist from day one so the vault is not retrofitted with governance after the
# canon has already sprawled.

# canon_flow appends one row per date on any run, so the history file seeds
# itself from first use and needs no scheduler.
CANON_SIZE_HISTORY_REL = "Resources/operator/canon-size-history.jsonl"
CANON_FLOW_WINDOW_DAYS = 7
CANON_FLOW_MIN_SPAN_DAYS = 5   # need >=2 rows at least this far apart to judge
CANON_FLOW_MAX_GROWTH = {      # chars per window; only files listed here are judged
    "Rules-of-Engagement.md": 1_500,
}

# rule_rent / roe_sunset: per-rule effectiveness data. rule-recurrences.jsonl
# records the case where a correction matches an EXISTING canon rule instead
# of earning a new one. A rule that recurs WHILE LOADED is evidence that prose
# is not preventing it, and the remedy is mechanical enforcement rather than
# restating it more firmly. A dated rule untouched for months with no
# recurrence is the opposite case: a displacement candidate.
RULE_RECURRENCES_REL = "Resources/operator/rule-recurrences.jsonl"
RULE_RENT_THRESHOLD = 2        # recurrences before a rule is flagged
ROE_SUNSET_DAYS = 180

# canon_rule_count: the operative unit for instruction-following reliability
# is the number of discrete rules, not characters. Frontier models hold near-
# perfect adherence to roughly 150-200 instructions and then degrade (IFScale,
# arXiv 2507.11538; Claude models decay LINEARLY, so every added rule costs
# adherence), and the errors at density are OMISSIONS -- rules silently
# skipped, not misread. Character count can shrink while rule count grows, so
# a size budget cannot see this. These numbers are a property of the model,
# not of any one vault, which is why they ship unchanged.
ROE_RULE_COUNT_BUDGET = (130, 150)  # (warn, fail)


def finding(check, severity, path, message, fix):
    return {"check": check, "severity": severity, "path": path,
            "message": message, "fix": fix}


def is_real_vault(vault):
    """Always False in this vendored copy.

    The source this was vendored from gates several sub-checks that probe
    machine-specific machinery living OUTSIDE the audited vault (a
    marketplace lockfile, root-file mirrors, a skills-index builder) on
    "is this literally my own vault". A vendored, genericized copy has no
    such vault to compare against — those sub-checks would only ever be
    meaningful for the one vault this was copied out of, which this copy
    will never audit. Returning False unconditionally keeps them inert by
    construction instead of by a hardcoded path (which would also leak that
    vault's name into every scaffold this skill produces).
    """
    return False


# --- checks ----------------------------------------------------------------

def check_root_files(vault):
    out = []
    for name in sorted(os.listdir(vault)):
        p = os.path.join(vault, name)
        if not os.path.isfile(p) or name.startswith("."):
            continue
        if name not in ROOT_FILE_ALLOWLIST:
            out.append(finding("root_files", "warn", name,
                               "unsanctioned file in vault root",
                               "file it per the root CLAUDE.md routing table, or add it to "
                               "ROOT_FILE_ALLOWLIST here with a reason"))
    return out


def check_routing(vault):
    out = []
    for name in sorted(os.listdir(vault)):
        p = os.path.join(vault, name)
        if not os.path.isdir(p) or name in ROUTING_EXEMPT_DIRS or name.startswith("."):
            continue
        if not os.path.exists(os.path.join(p, "CLAUDE.md")):
            out.append(finding("routing", "warn", name + "/",
                               "top-level folder has no CLAUDE.md routing file",
                               f"write {name}/CLAUDE.md describing what lives there and where new info lands"))
    return out


def check_obsidian_layer(vault):
    """The vault must open as a configured Obsidian vault, not a bare folder.

    This check exists because the scaffold's own root CLAUDE.md calls the
    vault "an Obsidian knowledge base", and for a long time nothing made
    that true. Note that `.obsidian` is in ROUTING_EXEMPT_DIRS and is
    skipped by the directory walkers: no other check in this file can see
    inside it, so its absence was invisible to a passing audit.
    """
    out = []
    cfg = os.path.join(vault, ".obsidian")

    if not os.path.isdir(cfg):
        return [finding("obsidian_layer", "fail", ".obsidian/",
                        "no Obsidian config: this opens as an unconfigured folder, "
                        "not as the vault the root CLAUDE.md claims it is",
                        "scaffold .obsidian/ from the vault-setup skill's references/obsidian/")]

    required = os.path.join(cfg, OBSIDIAN_REQUIRED)
    if not os.path.isfile(required):
        out.append(finding("obsidian_layer", "fail", f".obsidian/{OBSIDIAN_REQUIRED}",
                           "no core-plugin config: graph, backlinks, daily notes and "
                           "Bases are all left at Obsidian's defaults",
                           f"write .obsidian/{OBSIDIAN_REQUIRED} from references/obsidian/"))

    for name, consequence in sorted(OBSIDIAN_EXPECTED.items()):
        if not os.path.isfile(os.path.join(cfg, name)):
            out.append(finding("obsidian_layer", "warn", f".obsidian/{name}",
                               f"missing, so {consequence}",
                               f"write .obsidian/{name} from references/obsidian/"))

    # A CSS snippet named in appearance.json but absent on disk is worse than
    # no snippet: Obsidian silently renders nothing and the vault looks unstyled
    # with no indication why.
    appearance = os.path.join(cfg, "appearance.json")
    if os.path.isfile(appearance):
        try:
            with open(appearance, encoding="utf-8") as fh:
                enabled = json.load(fh).get("enabledCssSnippets", [])
        except (ValueError, OSError) as e:
            out.append(finding("obsidian_layer", "warn", ".obsidian/appearance.json",
                               f"does not parse: {str(e)[:60]}",
                               "fix the JSON; Obsidian will silently ignore the whole file"))
            enabled = []
        for snippet in enabled:
            snippet_path = os.path.join(cfg, "snippets", f"{snippet}.css")
            if not os.path.isfile(snippet_path):
                out.append(finding("obsidian_layer", "fail",
                                   f".obsidian/snippets/{snippet}.css",
                                   f"appearance.json enables the '{snippet}' snippet but the "
                                   "file is absent, so the vault renders unstyled with no error",
                                   f"write the snippet, or drop '{snippet}' from "
                                   "appearance.json's enabledCssSnippets"))

    # Home.md is what workspace.json opens on. A dangling pointer here means
    # the owner's first launch lands on a "file does not exist" pane.
    ws = os.path.join(cfg, "workspace.json")
    if os.path.isfile(ws) and not os.path.isfile(os.path.join(vault, "Home.md")):
        out.append(finding("obsidian_layer", "fail", "Home.md",
                           "workspace.json opens Home.md on launch but the note does not exist",
                           "write Home.md, or remove the seeded workspace.json"))

    return out


def _read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # a corrupt row never blinds the whole file
    except OSError:
        return []
    return rows


def check_canon_flow(vault):
    """Growth-RATE detector for the budgeted canon files.

    A size budget catches the canon being too big. This catches it getting big
    fast, which is the earlier and more useful signal: it means the admission
    gate is leaking, and the fix is upstream of any individual rule.

    Appends today's sizes to the history file (idempotent per date), then
    compares the newest row against the row nearest CANON_FLOW_WINDOW_DAYS
    older. Self-seeding: the first run writes a row and judges nothing.
    """
    out = []
    hist_path = os.path.join(vault, CANON_SIZE_HISTORY_REL)
    today = date.today().isoformat()
    sizes = {}
    for rel in CANON_BUDGETS:
        p = os.path.join(vault, rel)
        if os.path.exists(p):
            sizes[rel] = os.path.getsize(p)
    rows = _read_jsonl(hist_path)
    if not any(r.get("date") == today for r in rows):
        try:
            os.makedirs(os.path.dirname(hist_path), exist_ok=True)
            with open(hist_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"date": today, "sizes": sizes},
                                    separators=(",", ":")) + "\n")
            rows.append({"date": today, "sizes": sizes})
        except OSError:
            return [finding("canon_flow", "info", CANON_SIZE_HISTORY_REL,
                            "size history UNWRITABLE - growth NOT tracked this run",
                            "fix permissions on the history file")]
    dated = sorted((r for r in rows if r.get("date") and isinstance(r.get("sizes"), dict)),
                   key=lambda r: r["date"])
    if len(dated) < 2:
        return out  # self-seeding run: nothing to judge yet, by design
    newest = dated[-1]
    d_new = date.fromisoformat(newest["date"])
    baseline = None
    for r in dated[:-1]:
        span = (d_new - date.fromisoformat(r["date"])).days
        if span >= CANON_FLOW_MIN_SPAN_DAYS:
            baseline = r  # keep the LATEST row still >= the min span back
    if baseline is None:
        return out
    span = (d_new - date.fromisoformat(baseline["date"])).days
    for rel, max_growth in CANON_FLOW_MAX_GROWTH.items():
        then = baseline["sizes"].get(rel)
        now_ = newest["sizes"].get(rel)
        if then is None or now_ is None:
            continue
        # normalize to the window so a 14-day gap does not double the allowance
        grown = (now_ - then) * CANON_FLOW_WINDOW_DAYS / max(span, 1)
        if grown > max_growth:
            out.append(finding("canon_flow", "warn", rel,
                               f"grew ~{grown:,.0f} chars per {CANON_FLOW_WINDOW_DAYS} days "
                               f"({then:,} -> {now_:,} over {span}d) - the admission gate is leaking",
                               "review the newly added rules: a first-time correction belongs "
                               "in the lessons file, not in the always-loaded canon"))
    return out


def check_rule_rent(vault):
    """A rule with repeated recurrences WHILE LOADED is proof prose is not
    preventing it. The remedy is a hook or a detector, not a restatement."""
    rows = _read_jsonl(os.path.join(vault, RULE_RECURRENCES_REL))
    if not rows:
        return []
    counts = {}
    for r in rows:
        key = (r.get("rule") or "").strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    out = []
    for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n >= RULE_RENT_THRESHOLD:
            out.append(finding("rule_rent", "warn", RULE_RECURRENCES_REL,
                               f"rule recurred {n}x despite being loaded: {rule[:120]}",
                               "promote it to mechanical enforcement (a hook, or a check in "
                               "this file); prose restatement has already failed twice"))
    return out[:5]  # cap: the top offenders are the actionable ones


def check_canon_rule_count(vault):
    """Rule-COUNT budget for the operational rules file.

    Character budgets miss the operative variable: adherence degrades with the
    number of discrete rules (see ROE_RULE_COUNT_BUDGET's comment). A merge
    that saves 300 characters and a merge that removes one RULE are different
    events, and only this check sees the second.
    """
    roe_path = os.path.join(vault, "Rules-of-Engagement.md")
    try:
        lines = open(roe_path, encoding="utf-8").read().splitlines()
    except OSError:
        return []  # canon_budgets already fails loud on the missing file
    n = sum(1 for ln in lines
            if re.match(r"^- \*\*", ln) or re.match(r"^\d+\. \*\*", ln))
    warn, fail = ROE_RULE_COUNT_BUDGET
    if n >= fail:
        return [finding("canon_rule_count", "fail", "Rules-of-Engagement.md",
                        f"{n} discrete rules, at/over the {fail}-rule hard line "
                        f"(adherence degrades past ~150 instructions; the failure mode is "
                        f"omission, not misreading)",
                        "displace or MERGE rules; merging two rules buys adherence, "
                        "rewording buys nothing")]
    if n >= warn:
        return [finding("canon_rule_count", "warn", "Rules-of-Engagement.md",
                        f"{n} discrete rules, past the {warn}-rule tripwire (hard line {fail})",
                        "the next slim should merge or displace by COUNT, not by characters")]
    return []


def check_roe_sunset(vault):
    """Dated bullet rules older than ROE_SUNSET_DAYS with no recorded
    recurrence are displacement candidates. ONE aggregated info finding: this
    must never become permanent warn noise."""
    roe_path = os.path.join(vault, "Rules-of-Engagement.md")
    try:
        lines = open(roe_path, encoding="utf-8").read().splitlines()
    except OSError:
        return []  # canon_budgets already fails loud on the missing file
    recur_rows = _read_jsonl(os.path.join(vault, RULE_RECURRENCES_REL))
    recur_text = " ".join((r.get("rule") or "").lower() for r in recur_rows)
    today = date.today()
    aged = []
    for ln in lines:
        # Bullet rules only. A numbered rule is one the owner set explicitly
        # and worded themselves; those are never flagged for age.
        if not ln.startswith("- **"):
            continue
        dates = re.findall(r"\((?:[^)]*?)?(\d{4}-\d{2}-\d{2})", ln)
        if not dates:
            continue
        try:
            newest = max(date.fromisoformat(d) for d in dates)
        except ValueError:
            continue
        age = (today - newest).days
        if age < ROE_SUNSET_DAYS:
            continue
        lead = ln[4:].split("**")[0].strip().rstrip(".")
        if lead and lead[:30].lower() in recur_text:
            continue  # it recurred - rule_rent owns it, not sunset
        aged.append((age, newest.isoformat(), lead[:80]))
    if not aged:
        return []
    aged.sort(reverse=True)
    oldest = "; ".join(f"{lead} ({d})" for _age, d, lead in aged[:3])
    return [finding("roe_sunset", "info", "Rules-of-Engagement.md",
                    f"{len(aged)} dated rule(s) older than {ROE_SUNSET_DAYS} days with no "
                    f"recorded recurrence; oldest: {oldest}",
                    "displacement candidates for the next canon slim")]


def check_hub_triangle(vault):
    out = []
    projects = os.path.join(vault, "Projects")
    board_path = os.path.join(projects, "Projects.md")
    root_c = open(os.path.join(vault, "CLAUDE.md"), encoding="utf-8").read()
    board = open(board_path, encoding="utf-8").read() if os.path.exists(board_path) else ""
    for name in sorted(os.listdir(projects)):
        p = os.path.join(projects, name)
        if not os.path.isdir(p) or name == "__pycache__":
            continue
        hub = os.path.join(p, name + ".md")
        if not os.path.exists(hub):
            out.append(finding("hub_triangle", "fail", f"Projects/{name}/",
                               "project folder has no hub file",
                               f"create Projects/{name}/{name}.md from Projects/_template.md"))
            continue
        if name not in board:
            out.append(finding("hub_triangle", "warn", f"Projects/{name}/",
                               "project missing from the board Projects/Projects.md",
                               "add a board row (the board is authoritative)"))
        # Either heading counts. Gating on one literal string means renaming
        # the section silently disables this sub-check, and a passing run
        # cannot tell "no projects missing" from "never looked".
        has_root_list = any(h in root_c for h in ("## Active Projects", "## Projects"))
        if has_root_list and name not in root_c:
            out.append(finding("hub_triangle", "warn", f"Projects/{name}/",
                               "project missing from root CLAUDE.md Active Projects",
                               "add a one-line entry mirroring the board, or drop the "
                               "Active Projects section entirely (board-only is valid: "
                               "the board is authoritative)"))
    return out


def check_hub_yaml(vault):
    out = []
    try:
        import yaml
    except ImportError:
        return [finding("hub_yaml", "info", "-", "pyyaml unavailable; hub YAML NOT checked",
                        "pip install pyyaml (this run cannot tell — degrade loud, not silent)")]
    projects = os.path.join(vault, "Projects")
    for name in sorted(os.listdir(projects)):
        hub = os.path.join(projects, name, name + ".md")
        if not os.path.exists(hub):
            continue
        text = open(hub, encoding="utf-8").read()
        rel = f"Projects/{name}/{name}.md"
        if not text.startswith("---"):
            out.append(finding("hub_yaml", "fail", rel, "hub has no frontmatter",
                               "add type/status/last_touched/next_step frontmatter"))
            continue
        try:
            fm = yaml.safe_load(text.split("---")[1])
        except Exception as e:
            out.append(finding("hub_yaml", "fail", rel, f"frontmatter does not parse: {str(e)[:80]}",
                               "fix the YAML; prose fields use |- block scalars"))
            continue
        for key in ("status", "last_touched", "next_step"):
            if not fm or key not in fm:
                out.append(finding("hub_yaml", "warn", rel, f"frontmatter missing `{key}`",
                                   f"add `{key}` (hubs carry status, last_touched, next_step)"))
    return out


def check_hub_log_lag(vault):
    """A hub whose newest dated `## Log` entry is later than `last_touched`.

    A wrap written by hand, or by a tool that does not run the wrap skill,
    appends the Log body and skips the frontmatter, so the board and every
    "untouched 30+ days" reading work from a date the hub's own Log contradicts. Both Log heading shapes count (`- **DATE` and
    `### DATE`); a heading-only regex undercounts mixed hubs.
    """
    out = []
    today = date.today().isoformat()
    projects = os.path.join(vault, "Projects")
    entry = re.compile(r"^(?:[-*]\s+\*\*|#{3,4}\s+)(\d{4}-\d{2}-\d{2})\b", re.M)
    for name in sorted(os.listdir(projects)):
        hub = os.path.join(projects, name, name + ".md")
        if not os.path.exists(hub):
            continue
        text = open(hub, encoding="utf-8").read()
        m = re.search(r"^last_touched:\s*[\"']?(\d{4}-\d{2}-\d{2})", text, re.M)
        if not m:
            continue  # a missing field is hub_yaml's finding
        # Hubs keep history under `## Log`, `## Recent changes`, or one dated
        # `## Recent changes (DATE)` per session; the heading date counts too.
        dates = []
        for sec in re.finditer(r"^## (?:Log|Recent changes)\b([^\n]*)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
            dates += re.findall(r"\d{4}-\d{2}-\d{2}", sec.group(1))
            dates += entry.findall(sec.group(2))
        dates = [d for d in dates if d <= today]
        if dates and max(dates) > m.group(1):
            out.append(finding("hub_log_lag", "warn", f"Projects/{name}/{name}.md",
                               f"newest Log entry {max(dates)} is later than last_touched {m.group(1)}",
                               "set last_touched to the newest Log date and rewrite next_step "
                               "(the wrap step does both; a hand wrap skipped it)"))
    return out


LESSONS_REL = os.path.join("Tasks", "lessons.md")
LESSONS_LOOKBACK_DAYS = (7, 30, 90)
LESSONS_DROP_TOLERANCE = 3  # a dedupe may retire a few sections; a clobber retires dozens
_DATED_SECTION_RE = re.compile(r"^## 20\d\d-\d\d-\d\d", re.M)


def lessons_section_count(text):
    return len(_DATED_SECTION_RE.findall(text))


def lessons_floor_findings(vault, git=None):
    """Dated-section count of lessons.md against its own git past.

    A stale copy can overwrite the lessons file and remove months of sections
    while every other detector stays quiet, because they ask only whether the
    file exists or has grown, and after such a cut it keeps growing.
    The record is append-only, so the number of dated sections must never fall.
    Stateless on purpose: the baseline is git history, not a high-water file a
    second stale copy could also roll back. `git(args) -> str` is injectable so
    the test can seed a past without a repository.
    """
    path = os.path.join(vault, LESSONS_REL)
    if not os.path.exists(path):
        return []  # root_files / routing own a missing file
    now = lessons_section_count(open(path, encoding="utf-8").read())

    def _git(args):
        r = subprocess.run(["git", "-C", vault] + args, capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:120])
        return r.stdout

    git = git or _git
    out, measured = [], 0
    for days in LESSONS_LOOKBACK_DAYS:
        try:
            sha = git(["rev-list", "-1", "--before=%d days ago" % days, "HEAD"]).strip()
            if not sha:
                continue
            then = lessons_section_count(git(["show", "%s:%s" % (sha, LESSONS_REL.replace(os.sep, "/"))]))
        except Exception:
            continue
        measured += 1
        if now < then - LESSONS_DROP_TOLERANCE:
            out.append(finding("lessons_floor", "fail", "Tasks/lessons.md",
                               f"{now} dated sections now, {then} at {sha[:8]} ({days}d ago): "
                               f"{then - now} sections of an append-only record are gone",
                               f"union-merge from `git show {sha[:8]}:Tasks/lessons.md` (section-level, "
                               "never one side); then rebuild lessons-index and relay-startup-index"))
            break  # the nearest baseline that shows the loss is the one to restore from
    if not measured:
        out.append(finding("lessons_floor", "info", "Tasks/lessons.md",
                           "no git baseline readable; the section floor was NOT checked",
                           "run inside the vault's git repo (unknown is not clean)"))
    return out


def check_lessons_floor(vault):
    return lessons_floor_findings(vault)


def check_canon_budgets(vault):
    out = []
    for rel, (warn, fail) in CANON_BUDGETS.items():
        p = os.path.join(vault, rel)
        if not os.path.exists(p):
            out.append(finding("canon_budgets", "fail", rel, "budgeted canon file MISSING", "restore it"))
            continue
        n = os.path.getsize(p)
        if n >= fail:
            out.append(finding("canon_budgets", "fail", rel,
                               f"{n:,} chars, at/over the {fail:,} hard line",
                               "compress-or-displace NOW; never accrete"))
        elif n >= warn:
            out.append(finding("canon_budgets", "warn", rel,
                               f"{n:,} chars, past the {warn:,} tripwire (hard line {fail:,})",
                               "trim before the next rule lands"))
    return out


def check_generated_staleness(vault):
    out = []
    op = os.path.join(vault, "Resources", "operator")
    # relay-startup-index: vault-scoped (takes --vault, checks THIS vault's
    # own builder script and index), so this stays active and safe even
    # though is_real_vault() is always False above. It simply won't fire
    # unless this vault grows its own build-relay-startup-index.py.
    builder = os.path.join(op, "build-relay-startup-index.py")
    if os.path.exists(builder):
        r = subprocess.run([sys.executable, builder, "--vault", vault, "--check"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            out.append(finding("generated_staleness", "warn", "Tasks/relay-startup-index.md",
                               "stale against lessons.md: " + (r.stdout + r.stderr).strip()[:100],
                               f"python3 '{builder}'"))
    # The remaining sub-checks (a skills-index builder, a marketplace lockfile,
    # root-file mirrors) all probe machine-specific machinery outside the
    # audited vault and are gated on is_real_vault(), which is always False
    # here — see that function's docstring. Say so explicitly rather than
    # skip silently: a permanently-inert sub-check would otherwise read as
    # "checked and clean" (2026-08-18, the same principle that costs the
    # zero-inspection guard below its own info finding).
    out.append(finding("generated_staleness", "info", "-",
                       "3 sub-check(s) inert in this vendored copy (skills-index, marketplace "
                       "lock, root mirrors) — they audit machinery this vault does not have",
                       "re-add them, properly gated, if this vault grows equivalents of its own"))
    return out


def _newest_mtime(root):
    best = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            if f.endswith(".md"):
                try:
                    best = max(best, os.path.getmtime(os.path.join(dirpath, f)))
                except OSError:
                    pass
    return best


def load_pipelines(vault):
    """PIPELINES merged with this vault's own overlay.

    Returns (pipelines, findings). Degrades LOUD: a malformed or unreadable
    overlay yields a warn finding rather than silently falling back to the
    built-in table, because a silently-ignored overlay looks exactly like a
    correctly-empty one and would hide the owner's own pipeline settings.
    """
    merged = dict(PIPELINES)
    out = []
    path = os.path.join(vault, PIPELINES_OVERLAY_REL)
    if not os.path.exists(path):
        return merged, out
    try:
        with open(path) as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("top level must be an object")
    except Exception as exc:
        out.append(finding("pipeline_freshness", "warn", PIPELINES_OVERLAY_REL,
                           f"pipeline overlay unreadable: {type(exc).__name__}: {exc}",
                           "fix the JSON; until then the built-in table is in use "
                           "and this vault's own pipeline settings are NOT applied"))
        return merged, out
    for rel, spec in data.items():
        if not isinstance(spec, dict):
            out.append(finding("pipeline_freshness", "warn", PIPELINES_OVERLAY_REL,
                               f"overlay entry {rel!r} is not an object",
                               'use {"max_days": <int|null>, "note": "<str>"}'))
            continue
        max_days, note = merged.get(rel, (None, "no note"))
        if "max_days" in spec:
            max_days = spec["max_days"]
        if "note" in spec:
            note = spec["note"]
        merged[rel] = (max_days, note)
    return merged, out


def check_pipeline_freshness(vault):
    pipelines, out = load_pipelines(vault)
    now = time.time()
    for rel, (max_days, note) in pipelines.items():
        p = os.path.join(vault, rel)
        if not os.path.isdir(p):
            out.append(finding("pipeline_freshness", "warn", rel, "pipeline folder missing", note))
            continue
        newest = _newest_mtime(p)
        # An EMPTY folder and a STALE folder are different states and must read
        # differently: formatting float("inf") through {:.0f} printed the literal
        # "newest file infd old", which is gibberish in a report someone else reads.
        if not newest:
            out.append(finding("pipeline_freshness", "warn", rel,
                               "pipeline folder is empty (never written to)", note))
            continue
        age_d = (now - newest) / 86400
        if max_days is None:
            out.append(finding("pipeline_freshness", "info", rel,
                               f"newest file {age_d:.0f}d old (watch-only)", note))
        elif age_d > max_days:
            out.append(finding("pipeline_freshness", "warn", rel,
                               f"newest file {age_d:.0f}d old (> {max_days}d)",
                               f"pipeline is dark — {note}"))
    # Uncommitted work is a separate question from any scheduled-job health,
    # and only meaningful when the tree is actually dirty and this is a git repo.
    r = subprocess.run(["git", "-C", vault, "status", "--porcelain"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        dirty = len([l for l in r.stdout.splitlines() if l.strip()])
        c = subprocess.run(["git", "-C", vault, "log", "-1", "--format=%ct"],
                           capture_output=True, text=True, timeout=30)
        if c.returncode == 0 and c.stdout.strip():
            age_min = (now - int(c.stdout.strip())) / 60
            if age_min > AUTOSYNC_MAX_AGE_MIN:
                out.append(finding("pipeline_freshness", "warn", ".git",
                                   f"{dirty} uncommitted file(s) and no commit for {age_min:.0f}m",
                                   "commit or investigate why nothing is landing"))
    return out


def check_misfiled_backups(vault):
    """Snapshots belong in the root .backups/ only."""
    out = []
    root_backups = os.path.join(vault, ".backups")
    for dirpath, dirnames, filenames in os.walk(vault):
        if os.path.abspath(dirpath).startswith(os.path.abspath(root_backups)):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in (".git", ".obsidian", "__pycache__", "node_modules")]
        rel_dir = os.path.relpath(dirpath, vault)
        for d in list(dirnames):
            if d == ".backups" and rel_dir != ".":
                out.append(finding("misfiled_backups", "warn", os.path.join(rel_dir, d) + "/",
                                   "nested .backups directory outside the root .backups/",
                                   "move its files into the root .backups/ (path-encoded names) and remove it"))
                dirnames.remove(d)
        for f in filenames:
            if ".backup" in f and rel_dir != ".":
                out.append(finding("misfiled_backups", "warn", os.path.join(rel_dir, f),
                                   "backup-named file outside the root .backups/",
                                   "move it into the root .backups/"))
    return out


def check_inbox_aging(vault):
    out = []
    inbox = os.path.join(vault, "_inbox")
    if not os.path.isdir(inbox):
        return out
    now = time.time()
    for name in sorted(os.listdir(inbox)):
        p = os.path.join(inbox, name)
        if name in ("CLAUDE.md", "_processed") or name.startswith("quarantine"):
            continue
        if os.path.isfile(p):
            age_d = (now - os.path.getmtime(p)) / 86400
            if age_d > INBOX_MAX_AGE_DAYS:
                out.append(finding("inbox_aging", "warn", f"_inbox/{name}",
                                   f"{age_d:.0f}d old (> {INBOX_MAX_AGE_DAYS}d aging rule)",
                                   "route to its real home or _inbox/_processed/ with a disposition note"))
    return out


def check_todo_hygiene(vault):
    out = []
    p = os.path.join(vault, "Tasks", "todo.md")
    if not os.path.exists(p):
        return [finding("todo_hygiene", "fail", "Tasks/todo.md", "missing", "restore it")]
    text = open(p, encoding="utf-8").read()
    m = re.search(r"^## Active\n(.*?)(?=^## )", text, flags=re.M | re.S)
    if m:
        done = re.findall(r"^- (?:\[x\]|~~|\[ \] ~~)", m.group(1), flags=re.M)
        if done:
            out.append(finding("todo_hygiene", "warn", "Tasks/todo.md",
                               f"{len(done)} completed/struck item(s) still under ## Active",
                               "todo.md is forward-only: move shipped blocks to Tasks/journal.md"))
    return out


def check_size_claims(vault):
    """A canon claim about lessons.md's size must track the real file."""
    out = []
    actual_kt = os.path.getsize(os.path.join(vault, "Tasks", "lessons.md")) / 4 / 1000
    targets = ["CLAUDE.md"]
    for rel in targets:
        p = rel if os.path.isabs(rel) else os.path.join(vault, rel)
        if not os.path.exists(p):
            continue
        for m in re.finditer(r"~(\d+)k tokens", open(p, encoding="utf-8").read()):
            claimed = int(m.group(1))
            if abs(claimed - actual_kt) / max(actual_kt, 1) > 0.30:
                out.append(finding("size_claims", "warn", rel,
                                   f"claims ~{claimed}k tokens; lessons.md is ~{actual_kt:.0f}k",
                                   "update the figure where it lives (state assertions have a half-life)"))
    return out


def check_vitals_trend(vault):
    out = []
    p = os.path.join(vault, "Resources", "operator", "vault-state.json")
    if not os.path.exists(p):
        return [finding("vitals_trend", "info", "-", "vault-state.json missing — trend NOT checked",
                        "run a vitals tracker if one exists (degrade loud, not silent)")]
    trend = json.load(open(p)).get("vitals_trend", [])
    if len(trend) < 2:
        return [finding("vitals_trend", "info", "-", "not enough trend rows to judge", "-")]
    newest = trend[0]
    baseline = trend[min(VITALS_LOOKBACK_DAYS, len(trend) - 1)]
    for k in VITALS_METRICS:
        a, b = baseline.get(k), newest.get(k)
        if a is not None and b is not None and b > a:
            out.append(finding("vitals_trend", "warn", k,
                               f"{a} -> {b} over {VITALS_LOOKBACK_DAYS}d (worsening)",
                               "a tracked-but-unacted metric is rot with a dashboard — act on it"))
    return out


# --- zero-inspection guard --------------------------------------------------
# A check that walks a directory and inspects ZERO items still returns [] and
# reads as clean. Make every checker fail on zero inspections and prove it on
# seeded known-bads. Covers the checks that walk a directory tree and have
# no such guard of their own (canon_budgets, todo_hygiene, and size_claims
# already fail loud on a missing file by design).
ZERO_INSPECTION = {
    "hub_triangle": lambda vault: os.path.isdir(os.path.join(vault, "Projects"))
        and any(os.path.isdir(os.path.join(vault, "Projects", n)) and n != "__pycache__"
                for n in os.listdir(os.path.join(vault, "Projects"))),
    "misfiled_backups": lambda vault: os.path.isdir(vault) and len(os.listdir(vault)) > 0,
}


CHECKS = {
    "root_files": check_root_files,
    "routing": check_routing,
    "obsidian_layer": check_obsidian_layer,
    "canon_flow": check_canon_flow,
    "canon_rule_count": check_canon_rule_count,
    "roe_sunset": check_roe_sunset,
    "rule_rent": check_rule_rent,
    "hub_triangle": check_hub_triangle,
    "hub_yaml": check_hub_yaml,
    "hub_log_lag": check_hub_log_lag,
    "lessons_floor": check_lessons_floor,
    "canon_budgets": check_canon_budgets,
    "generated_staleness": check_generated_staleness,
    "pipeline_freshness": check_pipeline_freshness,
    "misfiled_backups": check_misfiled_backups,
    "inbox_aging": check_inbox_aging,
    "todo_hygiene": check_todo_hygiene,
    "size_claims": check_size_claims,
    "vitals_trend": check_vitals_trend,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None,
                    help="vault root; default: the SECOND_BRAIN_VAULT environment variable")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", help="comma-separated check names")
    args = ap.parse_args()
    args.vault = args.vault or os.environ.get("SECOND_BRAIN_VAULT")
    if not args.vault:
        print("SECOND_BRAIN_VAULT is not set and no --vault was given. Set it to the absolute "
              "path of your vault (see the plugin README).", file=sys.stderr)
        return 2
    args.vault = os.path.abspath(os.path.expanduser(args.vault))
    if not os.path.isdir(args.vault):
        print(f"vault not found: {args.vault} (check SECOND_BRAIN_VAULT or --vault)", file=sys.stderr)
        return 2

    names = list(CHECKS) if not args.only else [n.strip() for n in args.only.split(",")]
    findings, errors = [], []
    for n in names:
        if n not in CHECKS:
            print(f"unknown check: {n}", file=sys.stderr)
            return 2
        try:
            n_findings = CHECKS[n](args.vault)
        except Exception as e:  # a broken check is itself a loud finding, never silence
            errors.append(n)
            findings.append(finding(n, "info", "-", f"check CRASHED: {e!r} — this area NOT checked",
                                    "fix vault-audit.py; a permanently clean check may be pointing at nothing"))
            continue
        precond = ZERO_INSPECTION.get(n)
        if precond is not None and not n_findings and not precond(args.vault):
            findings.append(finding(n, "info", "-",
                "zero items inspected (target directory missing or empty) — this area "
                "NOT checked; a permanently clean result here would be indistinguishable "
                "from a real pass",
                "confirm the target directory exists and is populated as expected"))
        findings.extend(n_findings)

    sev_rank = {"fail": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (sev_rank[f["severity"]], f["check"]))
    if args.json:
        print(json.dumps({"date": date.today().isoformat(), "vault": args.vault,
                          "checks_run": names, "checks_crashed": errors,
                          "findings": findings}, indent=1))
    else:
        counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("fail", "warn", "info")}
        print(f"vault-audit {date.today().isoformat()} — {len(names)} checks: "
              f"{counts['fail']} fail, {counts['warn']} warn, {counts['info']} info")
        for f in findings:
            print(f"  [{f['severity'].upper():4}] {f['check']:<20} {f['path']}: {f['message']}")
            print(f"         fix: {f['fix']}")
    if any(f["severity"] == "fail" for f in findings):
        return 2
    if any(f["severity"] == "warn" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
