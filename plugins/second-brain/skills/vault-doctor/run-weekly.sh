#!/bin/bash
# run-weekly.sh - scheduled vault health run for the vault-doctor skill.
#
# Two phases, in order:
#   1. MECHANICAL SELF-TENDING. Only passes that are provably safe unattended:
#      relocate-misfiled-backups (moves snapshots into the root .backups/, never
#      deletes, path-encoded names, idempotent) and normalize-wikilinks --apply
#      (rewrites a link ONLY when it is currently dead AND the repair resolves to
#      exactly one real file; never touches the session/transcript layer).
#      Anything judgment-shaped (displacing canon, killing todo items, repointing
#      an ambiguous link, writing frontmatter that asserts status) stays OUT of
#      here and waits for a session. Set VAULT_DOCTOR_DETECT_ONLY=1 to skip
#      this phase.
#   2. DETECTION. vault-audit; findings become a dated _inbox/ report to walk with
#      the vault-doctor skill. Clean runs log only.
#
# Failure policy: a mechanical pass that fails is logged and does NOT stop the
# audit; detection is the job that must always run.
# Nothing installs this. Schedule it yourself (cron, launchd, a CI job) with
# SECOND_BRAIN_VAULT in the job's environment. A scheduled job that edits your
# vault is a standing change: install it deliberately.
set -uo pipefail
VAULT="${SECOND_BRAIN_VAULT:-}"
if [ -z "$VAULT" ]; then
    echo "SECOND_BRAIN_VAULT is not set. Set it to the absolute path of your vault (see the plugin README)." >&2
    exit 2
fi
if [ ! -d "$VAULT" ]; then
    echo "vault not found: $VAULT (check SECOND_BRAIN_VAULT)" >&2
    exit 2
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN="$(cd "$HERE/../.." && pwd)"
LOG="${VAULT_DOCTOR_LOG:-$VAULT/Resources/operator/vault-doctor.log}"
OP="$PLUGIN/operator"
AUDIT="$PLUGIN/skills/vault-setup/references/operator/vault-audit.py"
STAMP="$(date '+%Y-%m-%d-%H%M')"
PY="${PYTHON:-python3}"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$(dirname "$LOG")" "$VAULT/_inbox"

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $*" >>"$LOG"; }

# --- phase 1: mechanical self-tending -------------------------------------
MECH=""
if [ -z "${VAULT_DOCTOR_DETECT_ONLY:-}" ] && [ -f "$OP/relocate-misfiled-backups.py" ]; then
    if OUT_B="$("$PY" "$OP/relocate-misfiled-backups.py" --vault "$VAULT" --apply 2>&1)"; then
        log "mechanical: $OUT_B"
        case "$OUT_B" in *"MOVED"*) MECH="${MECH}${OUT_B}"$'\n';; esac
    else
        log "ERR mechanical relocate-misfiled-backups failed: $OUT_B"
    fi
fi
if [ -z "${VAULT_DOCTOR_DETECT_ONLY:-}" ] && [ -f "$OP/normalize-wikilinks.py" ]; then
    if OUT_L="$("$PY" "$OP/normalize-wikilinks.py" --vault "$VAULT" --apply 2>&1 | head -2)"; then
        log "mechanical: $(printf '%s' "$OUT_L" | tr '\n' ' ')"
        case "$OUT_L" in *"rewrites: 0"*) : ;; *) MECH="${MECH}${OUT_L}"$'\n';; esac
    else
        log "ERR mechanical normalize-wikilinks failed"
    fi
fi

# --- phase 2: detection ----------------------------------------------------
OUT="$("$PY" "$AUDIT" --vault "$VAULT" 2>&1)"
RC=$?
if [ "$RC" -eq 0 ] && [ -z "$MECH" ]; then
    log "PASS clean run, no mechanical changes"
    exit 0
fi
REPORT="$VAULT/_inbox/vault-doctor-$STAMP.md"
{
    echo "---"; echo "type: alert"; echo "date: $(date '+%Y-%m-%d')"
    echo "status: open"; echo "tags: [alert, vault-doctor]"; echo "---"; echo
    echo "# vault-doctor weekly (audit exit $RC)"; echo
    if [ -n "$MECH" ]; then
        echo "## Applied automatically (mechanical, safe-unattended)"; echo
        echo '```'; printf '%s' "$MECH"; echo '```'; echo
    fi
    if [ "$RC" -ne 0 ]; then
        echo "## Findings: run the vault-doctor skill in a session to walk these with fixes"; echo
        echo '```'; printf '%s\n' "$OUT"; echo '```'
    else
        echo "Audit clean; the entry above records what the mechanical phase changed."
    fi
} > "$REPORT"
log "REPORT exit $RC mech=$([ -n "$MECH" ] && echo yes || echo no) -> $REPORT"
exit 0
