#!/usr/bin/env python3
"""check_secret_shape.py - after a rotation, check each stored secret is shaped
right, without ever printing it.

  check_secret_shape.py FILE [FILE ...]        (.dev.vars, .env: NAME=VALUE lines)

Catches the mistakes that broke real rotations: a value that still carries its
own "NAME=" prefix (ElevenLabs, 2026-10-06: a BSD sed kept the prefix and every
call returned 401), surrounding quotes left in, a trailing CR or space, an empty
value, a placeholder, or a provider prefix that does not match the name
(an ANTHROPIC key that does not start sk-ant-). Values are read in-process and
compared; output is the NAME, the file:line and the problem. Never the value,
never a fragment of it.

Prints the ledger JSON. Exit 0 all PASS, 1 any FAIL, 3 nothing checkable.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
from ledger import result  # noqa: E402

PLACEHOLDER = re.compile(r"^(your[-_ ].*|xxx+|changeme|replace[-_ ]?me|todo|<.*>|\.\.\.|placeholder|example|test|dummy)$", re.I)
PREFIX = [  # (name pattern, required value prefix or regex, label)
    (r"ANTHROPIC", r"sk-ant-", "Anthropic keys start sk-ant-"),
    (r"OPENAI", r"sk-", "OpenAI keys start sk-"),
    (r"STRIPE.*SECRET|STRIPE_SK|STRIPE_KEY", r"[sr]k_(live|test)_", "Stripe secret keys start sk_live_/sk_test_ (or rk_)"),
    (r"STRIPE.*WEBHOOK", r"whsec_", "Stripe webhook secrets start whsec_"),
    (r"GOOGLE.*(MAPS|API)_?KEY|MAPS_?KEY|GEMINI.*KEY", r"AIza", "Google API keys start AIza"),
    (r"GITHUB.*(TOKEN|PAT)|GH_TOKEN", r"(gh[pousr]_|github_pat_)", "GitHub tokens start ghp_/github_pat_"),
    (r"SUPABASE.*(SERVICE|ANON).*KEY", r"(eyJ|sb_(secret|publishable)_)", "Supabase keys are JWTs (eyJ) or sb_ keys"),
]


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
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", v):
            problems.append("value starts with its own NAME= prefix")
        elif PLACEHOLDER.match(v):
            problems.append("placeholder, not a real value")
        else:
            for npat, vpat, label in PREFIX:
                if re.search(npat, name, re.I) and not re.match(vpat, v):
                    problems.append("prefix mismatch (%s)" % label)
                    break
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
