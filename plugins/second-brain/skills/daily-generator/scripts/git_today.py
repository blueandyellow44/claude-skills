#!/usr/bin/env python3
"""
git_today.py — emit a markdown fragment summarizing today's activity across
configured project folders.

Behavior:
  - Reads a JSON config for repo_paths and skip_patterns: --config PATH, else
    <vault>/Resources/operator/daily-generator.json when SECOND_BRAIN_VAULT is
    set and that file exists, else the example config.json next to this script
    (which lists no project folders).
  - For each repo_path:
      * If it is a real git repo, runs `git log --since=midnight ...` for the
        local-day range and emits commit lines.
      * If it is NOT a git repo (or git fails), falls back to listing files
        modified today (mtime check), with skip_patterns applied.
  - Returns a markdown fragment to stdout. Always exits 0 — never crashes.
  - Per-source errors go to stderr but do not fail the run.

Usage:
  python3 git_today.py [--config PATH] [--since-iso ISO_DATE]
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path


def expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def load_config(config_path: Path) -> dict:
    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"[git_today] config not found: {config_path}", file=sys.stderr)
        return {"repo_paths": [], "skip_patterns": []}
    except json.JSONDecodeError as e:
        print(f"[git_today] config malformed, falling back to defaults: {e}", file=sys.stderr)
        return {"repo_paths": [], "skip_patterns": []}

    if not isinstance(cfg, dict):
        print(f"[git_today] config not an object, falling back", file=sys.stderr)
        return {"repo_paths": [], "skip_patterns": []}

    cfg.setdefault("repo_paths", [])
    cfg.setdefault("skip_patterns", [])
    if not isinstance(cfg["repo_paths"], list):
        cfg["repo_paths"] = []
    if not isinstance(cfg["skip_patterns"], list):
        cfg["skip_patterns"] = []
    return cfg


def is_git_repo(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and r.stdout.strip() == "true"
    except Exception:
        return False


def git_commits_today(path: Path, since_iso: str) -> list[str]:
    """Return one-line commit messages from `path` since `since_iso` (local time)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "log",
             f"--since={since_iso}",
             "--pretty=format:%h %s",
             "--no-merges"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return []
        return [line for line in r.stdout.splitlines() if line.strip()]
    except Exception as e:
        print(f"[git_today] git log failed for {path}: {e}", file=sys.stderr)
        return []


def files_modified_today(path: Path, skip_patterns: list[str], since_ts: float, max_results: int = 25) -> list[str]:
    """Walk path and return files with mtime >= since_ts, applying skip_patterns."""
    results: list[str] = []
    if not path.is_dir():
        return results
    try:
        for root, dirs, files in os.walk(path):
            # Apply skip patterns to directory descent
            dirs[:] = [d for d in dirs if not any(p in d for p in skip_patterns)]
            for f in files:
                if any(p in f for p in skip_patterns):
                    continue
                fp = Path(root) / f
                try:
                    if fp.stat().st_mtime >= since_ts:
                        results.append(str(fp.relative_to(path)))
                        if len(results) >= max_results:
                            return results
                except Exception:
                    continue
    except Exception as e:
        print(f"[git_today] walk failed for {path}: {e}", file=sys.stderr)
    return results


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    default_config = here / "config.json"
    vault = os.environ.get("SECOND_BRAIN_VAULT")
    if vault:
        own = Path(os.path.expanduser(vault)) / "Resources" / "operator" / "daily-generator.json"
        if own.is_file():
            default_config = own
    ap.add_argument("--config", type=Path, default=default_config)
    ap.add_argument("--since-iso", type=str, default=None,
                    help="ISO timestamp of local midnight today; auto-computed if omitted")
    args = ap.parse_args()

    cfg = load_config(args.config)
    repo_paths = cfg.get("repo_paths", [])
    skip_patterns = cfg.get("skip_patterns", [])

    if args.since_iso:
        since_iso = args.since_iso
        try:
            since_dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
            since_ts = since_dt.timestamp()
        except Exception:
            since_dt = datetime.combine(datetime.now().date(), time.min)
            since_ts = since_dt.timestamp()
    else:
        since_dt = datetime.combine(datetime.now().date(), time.min)
        since_iso = since_dt.isoformat()
        since_ts = since_dt.timestamp()

    print(f"<!-- git_today.py: scanning since {since_iso} -->")

    if not repo_paths:
        print(f"- (no project paths configured in {args.config})")
        return 0

    any_activity = False
    for raw in repo_paths:
        path = expand(raw)
        label = raw.replace(os.path.expanduser("~"), "~") if isinstance(raw, str) else str(path)

        if not path.exists():
            print(f"- **{label}**: path not found, skipped")
            continue

        if is_git_repo(path):
            commits = git_commits_today(path, since_iso)
            if commits:
                any_activity = True
                print(f"- **{label}** ({len(commits)} commits):")
                for c in commits[:10]:
                    print(f"    - {c}")
                if len(commits) > 10:
                    print(f"    - (+ {len(commits) - 10} more)")
            else:
                print(f"- **{label}**: no commits today")
        else:
            modified = files_modified_today(path, skip_patterns, since_ts)
            if modified:
                any_activity = True
                print(f"- **{label}** (not a git repo, {len(modified)} files modified today):")
                for f in modified[:10]:
                    print(f"    - {f}")
                if len(modified) > 10:
                    print(f"    - (+ {len(modified) - 10} more)")
            else:
                print(f"- **{label}**: no activity today")

    if not any_activity:
        print("\n*(no project activity detected today)*")

    return 0


if __name__ == "__main__":
    sys.exit(main())
