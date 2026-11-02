#!/usr/bin/env python3
"""check_secret_shape.py - after a rotation, check each stored secret is shaped
right, without ever printing it.

  check_secret_shape.py FILE [FILE ...]        (.dev.vars, .env: NAME=VALUE lines)

Catches the mistakes that broke real rotations: a value that still carries its
own "NAME=" prefix (ElevenLabs, 2026-10-06: a BSD sed kept the prefix and every
call returned 401; a base64 value's trailing = padding is not a prefix),
surrounding quotes left in, a trailing CR or space, an empty value, a
placeholder (a word like test or changeme only under a secret-looking name, a
shape like xxxx or <paste> under any name, and a provider prefix followed by a
template's x's), or a provider prefix that does not match the name (an
ANTHROPIC key that does not start sk-ant-; an sk-ant- key in an OPENAI slot).
When several provider rules name one variable, the most specific wins, so a
whsec_ value under STRIPE_WEBHOOK_SECRET is right. Values are read in-process
and compared; output is the NAME, the file:line and the problem. Never the
value, never a fragment of it.

Prints the ledger JSON. Exit 0 all PASS, 1 any FAIL, 3 nothing checkable.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
from ledger import result  # noqa: E402

# Placeholder WORDS (test, example, changeme, your-key-here) only mean "no real value" under a
# name that looks like a secret: APP_ENV=test is a setting. Structural placeholders (<paste>,
# ..., xxxx) are never a real value under any name.
PLACEHOLDER_WORD = re.compile(r"^(your[-_ ].*|changeme|replace[-_ ]?me|todo|placeholder|example|test|dummy)$", re.I)
PLACEHOLDER_SHAPE = re.compile(r"^(x{3,}|<.*>|\.\.\.|\*{3,})$", re.I)
SECRET_NAME = re.compile(r"(?i)(key|secret|token|passw|pwd|credential|auth|private|salt|dsn)")
# (name pattern, required value regex, label). When several name patterns match one NAME, the most
# specific wins: the pattern that spells out the most letters of the name (STRIPE.*WEBHOOK beats
# STRIPE.*SECRET for STRIPE_WEBHOOK_SECRET). A rule is never chosen by list position alone.
PREFIX = [
    (r"ANTHROPIC", r"sk-ant-", "Anthropic keys start sk-ant-"),
    (r"OPENAI", r"sk-(?!ant-)", "OpenAI keys start sk- (sk-ant- is an Anthropic key)"),
    (r"STRIPE.*SECRET", r"[sr]k_(live|test)_", "Stripe secret keys start sk_live_/sk_test_ (or rk_)"),
    (r"STRIPE_SK", r"[sr]k_(live|test)_", "Stripe secret keys start sk_live_/sk_test_ (or rk_)"),
    (r"STRIPE_KEY", r"[sr]k_(live|test)_", "Stripe secret keys start sk_live_/sk_test_ (or rk_)"),
    (r"STRIPE.*WEBHOOK", r"whsec_", "Stripe webhook secrets start whsec_"),
    (r"GOOGLE.*(MAPS|API)_?KEY", r"AIza", "Google API keys start AIza"),
    (r"MAPS_?KEY", r"AIza", "Google API keys start AIza"),
    (r"GEMINI.*KEY", r"AIza", "Google API keys start AIza"),
    (r"GITHUB.*(TOKEN|PAT)", r"(gh[pousr]_|github_pat_)", "GitHub tokens start ghp_/github_pat_"),
    (r"GH_TOKEN", r"(gh[pousr]_|github_pat_)", "GitHub tokens start ghp_/github_pat_"),
    (r"SUPABASE.*(SERVICE|ANON).*KEY", r"(eyJ|sb_(secret|publishable)_)", "Supabase keys are JWTs (eyJ) or sb_ keys"),
]
# The provider prefix itself, so the part AFTER it can be tested for a template's x's.
PROVIDER_HEAD = re.compile(r"^(sk-ant-api\d\d-|sk-proj-|sk-|[sr]k_(live|test)_|whsec_|AIza|gh[pousr]_|github_pat_|sb_(secret|publishable)_|eyJ)")


def _specificity(name_pattern):
    """How much of the variable name a pattern spells out: its count of letters."""
    return sum(c.isalpha() for c in name_pattern)


def prefix_rule(name):
    """The most specific PREFIX rule whose name pattern matches NAME, or None."""
    hits = [rule for rule in PREFIX if re.search(rule[0], name, re.I)]
    return max(hits, key=lambda rule: _specificity(rule[0])) if hits else None


def is_placeholder(name, v):
    """Shape placeholders under any name; word placeholders only under a secret-looking name;
    a provider prefix followed by nothing but a template's x's or dots under either."""
    if PLACEHOLDER_SHAPE.match(v):
        return True
    if SECRET_NAME.search(name) and PLACEHOLDER_WORD.match(v):
        return True
    head = PROVIDER_HEAD.match(v)
    if head:
        rest = v[head.end():]
        if not rest or PLACEHOLDER_SHAPE.match(rest) or PLACEHOLDER_WORD.match(rest) or len(set(rest.lower())) == 1:
            return True
    return False


# A value that still carries its own NAME= prefix: an env-style name, "=", then MORE value. The "="
# that ends a base64 value (padding, followed by nothing or another "=") is not a prefix.
OWN_NAME_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=(?!=*$)")


def check_file(path):
    out = []
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    except OSError as exc:
        return [result("shape.%s" % os.path.basename(path), "Secrets file readable", "UNKNOWN", path, reason=str(exc))]
    for i, raw in enumerate(lines, 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", raw)
        if not m:
            continue
        name, val = m.group(1), m.group(2)
        where = "%s:%d" % (os.path.basename(path), i)
        cid = "shape.%s" % name
        problems = []
        if val.endswith("\r") or val != val.rstrip(" \t\r"):
            problems.append("trailing whitespace or CR")
        v = val.strip(" \t\r")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        elif v[:1] in "'\"" or v[-1:] in "'\"":
            problems.append("unbalanced quote")
        if not v:
            problems.append("empty value")
        elif OWN_NAME_PREFIX.match(v):
            problems.append("value starts with its own NAME= prefix")
        elif is_placeholder(name, v):
            problems.append("placeholder, not a real value")
        else:
            rule = prefix_rule(name)
            if rule and not re.match(rule[1], v):
                problems.append("prefix mismatch (%s)" % rule[2])
        if problems:
            out.append(result(cid, "%s is shaped right" % name, "FAIL", where, severity="high",
                              fix="re-store %s with a parser (python re), never sed; redeploy and make one live call" % name,
                              detail="; ".join(problems)))
        else:
            out.append(result(cid, "%s is shaped right" % name, "PASS", where + ": no prefix, quote, whitespace or placeholder problem"))
    return out


def main():
    files = sys.argv[1:]
    if not files:
        print("usage: check_secret_shape.py FILE [FILE ...]", file=sys.stderr)
        return 2
    res = []
    for f in files:
        res += check_file(f)
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
