#!/usr/bin/env python3
"""check_secrets.py - the ledger form of the secret scan.

  check_secrets.py REPO [--extra-dir DIR ...]

Runs scan_secrets.sh (gitleaks, proven on planted fake keys first, values
redacted) over the git history (or the files, outside git) and each extra
folder, and checks that secrets files are ignored and untracked. Prints the
ledger JSON. Never opens a secrets file; it only asks git about its path.

Secrets files by name: .dev.vars, .env and every dotted variant
(.env.production.local), .envrc, *.pem, *.key, *.p12, *.pfx, ssh id_* files,
credentials.json, service-account*.json, .npmrc; templates (.example and
friends) and dotenv-vault's encrypted .env.vault are not secrets files.
Generic-rule hits are classified in-process with the value never shown: a
value that is lowercase words is an identifier; so is a hex, UUID or pk_ value
whose VARIABLE says identifier, cache, idempotency or publishable, as long as
the value carries no provider prefix. Hex and UUID values under any other name
are kept (Heroku and Postmark keys look like that). A repo-side allowlist is
.gitleaksignore, .gitleaks.toml, or a gitleaks:allow comment that follows code
on the same line in any text file; prose that mentions the word is not one.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
from ledger import result  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# Secrets files by NAME: .dev.vars, .env with any number of dotted suffixes (.env.production.local),
# direnv's .envrc, key material (*.pem, *.key, *.p12, *.pfx, ssh id_* files), credential JSON, .npmrc.
SECRET_FILES = re.compile(r"^(\.dev\.vars|\.env(\.[A-Za-z0-9_-]+)*|\.envrc|.*\.(pem|key|p12|pfx)|id_(rsa|dsa|ecdsa|ed25519)"
                          r"|credentials\.json|service-account.*\.json|\.npmrc)$")
TEMPLATE = re.compile(r"\.(example|sample|template|dist|defaults)$")
# Names that match SECRET_FILES but are designed to be committed: dotenv-vault's .env.vault is the
# ENCRYPTED artifact (the DOTENV_KEY that opens it lives elsewhere).
NOT_SECRET_FILES = {".env.vault"}


def is_secret_file(path):
    """True when the basename says secrets file and is not a template or a committed-by-design artifact."""
    name = os.path.basename(path)
    return bool(SECRET_FILES.match(name)) and not TEMPLATE.search(name) and name not in NOT_SECRET_FILES
SUMMARY = re.compile(r"^(git history of|files in) (.+?): (\d+) finding\(s\)$")



def _dir_tag(repo, where):
    """A distinct, readable id per scanned folder: dist and app/dist never share one."""
    import hashlib
    where = where.rstrip("/")
    if where.startswith(repo + os.sep):
        return os.path.relpath(where, repo).replace("/", "_").lstrip(".")
    return "%s-%s" % (os.path.basename(where).lstrip("."), hashlib.sha1(where.encode()).hexdigest()[:6])


def scan(repo, extra):
    r = subprocess.run(["bash", os.path.join(HERE, "scan_secrets.sh"), repo] + extra, capture_output=True, text=True)
    out = r.stdout
    if r.returncode == 2 or "DETECTOR NOT PROVEN" in out or "not installed" in out:
        reason = (out.strip().splitlines() or ["scan could not run"])[-1]
        return [result("secrets.scan", "Secret scan", "UNKNOWN", "secure-secrets/scripts/scan_secrets.sh",
                       reason=reason + " (brew install gitleaks)")]
    res, block = [], None
    for line in out.splitlines():
        m = SUMMARY.match(line)
        if m:
            where = m.group(2)
            cid = "secrets.history" if (m.group(1) == "git history of" or where == repo) else "secrets.files." + _dir_tag(repo, where)
            block = {"id": cid, "where": where, "n": int(m.group(3)), "rows": []}
            res.append(block)
        elif block is not None and line.startswith("  "):
            block["rows"].append(line.strip())
    out_results = []
    for b in res:
        title = "No secrets in %s" % ("git history" if b["id"] == "secrets.history" else b["where"])
        if b["n"] == 0:
            out_results.append(result(b["id"], title, "PASS", "gitleaks (detector proven on planted keys): 0 findings in %s" % b["where"]))
            continue
        kept, dismissed = classify(repo, b)
        if kept is None:  # the classification pass did not run: report the raw count, never fewer
            kept, dismissed = b["rows"], 0
        if not kept:
            out_results.append(result(b["id"], title, "PASS", "gitleaks: %d hit(s), all generic-rule identifiers" % dismissed,
                                      detail="%d generic-api-key hit(s) dismissed as identifiers (lowercase words with no key-like character mix, or a variable named identifier/cache/idempotency/publishable holding a value with no provider prefix); classified in-process, no value shown" % dismissed))
        else:
            out_results.append(result(b["id"], title, "FAIL", ledger.join_hits(kept, 8, "; "), severity="high",
                                      fix="classify each hit with the value masked; rotate any real one (secret-rotation skill) and purge it from history",
                                      detail="%d finding(s) kept, %d generic-rule identifier(s) dismissed; rule and file shown, values never printed" % (len(kept), dismissed)))
    if not out_results:
        out_results.append(result("secrets.scan", "Secret scan", "UNKNOWN", "scan_secrets.sh", reason="scan produced no summary line"))
    return out_results


IDENT = re.compile(r"[a-z0-9]+(?:[._\-][a-z0-9]+)+")


HEXISH = re.compile(r"[0-9a-fA-F\-.]+")

# The variable the generic rule matched on: the identifier that precedes the separator in
# gitleaks' Match text (idempotencyKey": "..., cacheKey: '..., STRIPE_PUBLISHABLE_KEY = '...).
MATCH_NAME = re.compile(r"^\s*[\"'`]?([A-Za-z_][A-Za-z0-9_.-]*)")
# A name that says the value is an identifier, not a credential. A name that ALSO says
# secret/token/password/private/credential is never an identifier, whatever else it says.
IDENTIFIER_NAME = re.compile(r"(?i)(idempoten|cache|publishable|identifier)")
CREDENTIAL_NAME = re.compile(r"(?i)(secret|token|passw|private|credential)")
# Provider prefixes: a value carrying one is a key whatever its variable is called.
# pk_ (Stripe publishable) is deliberately absent: Stripe designs it to be public.
PROVIDER_PREFIX = re.compile(r"^(sk[-_]|rk_|whsec_|AIza|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|ASIA|npm_|glpat-|eyJ|hf_|r8_|SG\.|re_|shp(at|ss)_|dop_v1_|sq0|-----BEGIN)")


def identifier_shaped(s):
    """A generic-rule match that cannot be a credential by its VALUE alone: dotted or
    kebab lowercase words (radius.prefs.v1), or letters and underscores with no digit
    and no mixed case. Never a hex or UUID shape, never more than two digits. Real keys
    mix classes; provider-specific rules are never dismissed."""
    digits = sum(c.isdigit() for c in s)
    if HEXISH.fullmatch(s) or digits > 2:
        return False  # UUIDs and hex tokens are real key formats (Heroku, Postmark): never dismissed by value
    if IDENT.fullmatch(s):
        return True
    has_digit = digits > 0
    mixed = any(c.islower() for c in s) and any(c.isupper() for c in s)
    return not has_digit and not mixed


def identifier_named(match, secret):
    """A generic-rule hit whose VARIABLE says identifier (idempotencyKey, cacheKey,
    STRIPE_PUBLISHABLE_KEY) and whose value carries no provider prefix: a dedupe id,
    a content hash or a public key, not a leak. The variable never dismisses a
    secret/token/password name, and never a value that starts like a real key
    (sk_live_ in the publishable slot is still a leak)."""
    m = MATCH_NAME.match(match or "")
    if not m:
        return False
    name = m.group(1)
    if not IDENTIFIER_NAME.search(name) or CREDENTIAL_NAME.search(name):
        return False
    return not PROVIDER_PREFIX.match(secret or "")


def classify(repo, block):
    """Re-run gitleaks for one scope WITHOUT redaction into a private temp dir,
    decide each generic-api-key hit in-process, delete the report. Returns
    (kept rows as 'RULE  FILE  xN', number dismissed), or (None, 0) if it could
    not run. Never prints or returns a value."""
    import collections, json, shutil, tempfile
    work = tempfile.mkdtemp(prefix="sl-classify-")
    os.chmod(work, 0o700)
    try:
        rep = os.path.join(work, "r.json")
        mode = ["git"] if block["id"] == "secrets.history" and subprocess.run(["git", "-C", repo, "rev-parse", "--git-dir"], capture_output=True).returncode == 0 else ["dir"]
        os.makedirs(os.path.join(work, "noignore"))
        src = block["where"]
        if mode == ["git"] and os.path.exists(os.path.join(src, ".gitleaksignore")):
            # gitleaks honors the source's own .gitleaksignore whatever -i says: scan a clone without it
            subprocess.run(["git", "clone", "-q", "--no-hardlinks", src, os.path.join(work, "clone")], capture_output=True)
            if os.path.isdir(os.path.join(work, "clone")):
                try:
                    os.remove(os.path.join(work, "clone", ".gitleaksignore"))
                except OSError:
                    pass
                src = os.path.join(work, "clone")
        subprocess.run(["gitleaks"] + mode + [src, "-c", os.path.join(HERE, "gitleaks-suite.toml"), "-i", os.path.join(work, "noignore"),
                        "--ignore-gitleaks-allow", "--redact=0", "--no-banner", "-f", "json", "-r", rep], capture_output=True)
        try:
            found = json.load(open(rep))
        except (OSError, ValueError):
            return None, 0
        finally:
            if os.path.exists(rep):
                os.remove(rep)
        kept, dismissed = collections.Counter(), 0
        for f in found:
            if f.get("RuleID") == "generic-api-key" and (identifier_shaped(f.get("Secret") or "")
                                                         or identifier_named(f.get("Match"), f.get("Secret"))):
                dismissed += 1
            else:
                kept[(f.get("RuleID"), f.get("File"))] += 1
        return ["%s  %s  x%d" % (r, fl, n) for (r, fl), n in kept.most_common(40)], dismissed
    finally:
        shutil.rmtree(work, ignore_errors=True)


def ignored(repo):
    if subprocess.run(["git", "-C", repo, "rev-parse", "--git-dir"], capture_output=True).returncode != 0:
        return [result("secrets.ignored", "Secrets files are git-ignored", "UNKNOWN", repo, reason="not a git repo")]
    tracked = subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.splitlines()
    bad_tracked = [p for p in tracked if is_secret_file(p)]
    present = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", ".backups", ".wrangler", ".next", ".open-next")]
        for n in names:
            if is_secret_file(n):
                present.append(os.path.relpath(os.path.join(root, n), repo))
    not_ignored = []
    for p in present:
        if p in bad_tracked:
            continue
        if subprocess.run(["git", "-C", repo, "check-ignore", "-q", p], capture_output=True).returncode != 0:
            not_ignored.append(p)
    out = []
    if bad_tracked:
        out.append(result("secrets.tracked", "No secrets file is committed", "FAIL", ledger.join_hits(bad_tracked, 6, ", "), severity="critical",
                          fix="git rm --cached the file, add it to .gitignore, rotate every key it held, purge history"))
    else:
        out.append(result("secrets.tracked", "No secrets file is committed", "PASS", "git ls-files: none of .dev.vars/.env*/.envrc/pem/key/p12/id_rsa/credentials tracked"))
    if not_ignored:
        out.append(result("secrets.ignored", "Secrets files are git-ignored", "FAIL", ledger.join_hits(not_ignored, 6, ", "), severity="high",
                          fix="add the file name to .gitignore before the next git add"))
    else:
        out.append(result("secrets.ignored", "Secrets files are git-ignored", "PASS",
                          "git check-ignore: %s" % (ledger.join_hits(present, 6, ", ") + " ignored" if present else "no secrets file present")))
    return out



# gitleaks honors gitleaks:allow only as a comment on the LINE of a finding. An inline allow is
# code, then a comment marker, then the word; a line that is only the comment, or prose that
# quotes the word (`gitleaks:allow` in CONTRIBUTING.md), silences nothing.
ALLOW_MARKER = re.compile(r"(#|//|/\*|--|<!--|;)\s*gitleaks:allow\b")


def inline_allow(text):
    """True when some line carries code followed by a gitleaks:allow comment."""
    for line in text.splitlines():
        if "gitleaks:allow" not in line:
            continue
        m = ALLOW_MARKER.search(line)
        if m and line[:m.start()].strip():
            return True
    return False


def allowlists(repo):
    """A repo's own gitleaks allowlists hide hits from any scanner that honors them.
    The suite ignores them; this result says they exist so a human reads them.
    Every text file is read (.tf, .go, .rb, .vue included); binaries are skipped."""
    found = [f for f in (".gitleaksignore", ".gitleaks.toml", ".gitleaks.yml") if os.path.exists(os.path.join(repo, f))]
    for root, dirs, names in os.walk(repo):
        # The suite's own ledger (security/findings.md and friends) quotes this check's wording, so a repo that keeps
        # its ledger would match itself; the output folder is never an allowlist.
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git") and not d.startswith(".") and not (root == repo and d == "security")]
        for n in names:
            p = os.path.join(root, n)
            try:
                with open(p, "rb") as fh:
                    raw = fh.read(1_000_000)
            except OSError:
                continue
            if b"\x00" in raw[:8192] or b"gitleaks:allow" not in raw:
                continue
            if inline_allow(raw.decode("utf-8", errors="replace")):
                found.append("%s (gitleaks:allow)" % os.path.relpath(p, repo))
        if len(found) > 20:
            break
    if found:
        return [result("secrets.allowlist", "No repo-side gitleaks allowlist", "FAIL", ledger.join_hits(found, 6, ", "), severity="low",
                       fix="read each allowlisted hit with the value masked; the suite scans past them, other scanners do not",
                       detail="the suite ignores these (own config, empty ignore path, --ignore-gitleaks-allow)")]
    return [result("secrets.allowlist", "No repo-side gitleaks allowlist", "PASS", "no .gitleaksignore, .gitleaks.toml or gitleaks:allow comment")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--extra-dir", action="append", default=[])
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    extra = [os.path.join(repo, d) if not os.path.isabs(d) else d for d in a.extra_dir]
    return ledger.emit(scan(repo, extra) + ignored(repo) + allowlists(repo))


if __name__ == "__main__":
    sys.exit(main())
