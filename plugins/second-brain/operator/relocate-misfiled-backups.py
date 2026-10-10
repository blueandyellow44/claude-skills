#!/usr/bin/env python3
"""relocate-misfiled-backups.py — move stray snapshots into the root .backups/.

WHY. The vault's rule is a timestamped snapshot before any canonical edit, and
sessions write those snapshots wherever they are working: Tasks/.backups/,
Daily/.backups-*, nested .backups/ dirs across Projects/ and Skills/. A metrics
scan that counts them as curated notes gets worse with every rule-following
snapshot. vault-vitals skips .backups for that reason; this script fixes the
placement, so backups stay recoverable in ONE known location.

SAFETY. This never deletes and never touches file CONTENT. It moves a file into
.backups/relocated-<date>/ under a path-encoded name (Tasks__.backups__todo.md),
so the original location is recoverable from the name alone. A name collision is
suffixed, never overwritten. Empty .backups dirs left behind are removed; a dir
with anything else in it is left alone and reported.

Idempotent: a second run finds nothing and exits 0.

Usage:
    python3 relocate-misfiled-backups.py [--vault PATH] [--apply]
The vault is --vault, else the SECOND_BRAIN_VAULT environment variable; with
neither the script stops with a message (exit 1). Dry-run by default. Exit 0 always (a scheduled caller must not be blocked by it);
counts go to stdout for the log.
"""

import argparse
import os
import sys
from datetime import date

SKIP_TOP = {".git", ".obsidian", "node_modules", "__pycache__", ".trash"}


def is_backupish(name):
    """A file whose NAME marks it as a snapshot artifact."""
    low = name.lower()
    return ".backup" in low or low.startswith("backup-") or low.endswith(".bak")


def find_misfiled(vault):
    """Yield (abs_path, vault_relative_path) for every snapshot outside root .backups/."""
    root_backups = os.path.abspath(os.path.join(vault, ".backups"))
    for dirpath, dirnames, filenames in os.walk(vault):
        abs_dir = os.path.abspath(dirpath)
        if abs_dir == root_backups or abs_dir.startswith(root_backups + os.sep):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_TOP]
        rel_dir = os.path.relpath(dirpath, vault)
        in_nested_backups = ".backups" in rel_dir.split(os.sep)
        for f in filenames:
            if in_nested_backups or is_backupish(f):
                p = os.path.join(dirpath, f)
                yield p, os.path.relpath(p, vault)


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
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    dest_dir = os.path.join(vault, ".backups", f"relocated-{date.today().isoformat()}")
    items = list(find_misfiled(vault))
    if not items:
        print("[relocate-backups] OK nothing misfiled")
        return 0

    if args.apply:
        os.makedirs(dest_dir, exist_ok=True)
    moved = 0
    for src, rel in items:
        flat = rel.replace(os.sep, "__")
        dest = os.path.join(dest_dir, flat)
        if args.apply:
            n = 1
            while os.path.exists(dest):          # never overwrite a prior snapshot
                dest = os.path.join(dest_dir, f"{flat}.{n}")
                n += 1
            os.replace(src, dest)
        moved += 1

    removed_dirs, kept_dirs = 0, []
    if args.apply:
        root_backups = os.path.abspath(os.path.join(vault, ".backups"))
        for dirpath, dirnames, filenames in os.walk(vault, topdown=False):
            abs_dir = os.path.abspath(dirpath)
            if abs_dir == root_backups or abs_dir.startswith(root_backups + os.sep):
                continue
            if os.path.basename(dirpath) != ".backups":
                continue
            leftovers = [f for f in os.listdir(dirpath)] if os.path.isdir(dirpath) else []
            if not leftovers:
                os.rmdir(dirpath)
                removed_dirs += 1
            else:
                # empty subdirs are fine to prune; anything else is reported, never touched
                for sub in list(leftovers):
                    subp = os.path.join(dirpath, sub)
                    if os.path.isdir(subp) and not os.listdir(subp):
                        os.rmdir(subp)
                if os.path.isdir(dirpath) and not os.listdir(dirpath):
                    os.rmdir(dirpath)
                    removed_dirs += 1
                else:
                    kept_dirs.append(os.path.relpath(dirpath, vault))

    tag = "MOVED" if args.apply else "DRY-RUN would move"
    print(f"[relocate-backups] {tag} {moved} file(s) -> .backups/relocated-{date.today().isoformat()}/"
          + (f", removed {removed_dirs} empty nested .backups dir(s)" if args.apply else ""))
    for d in kept_dirs:
        print(f"[relocate-backups] LEFT ALONE (not empty): {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
