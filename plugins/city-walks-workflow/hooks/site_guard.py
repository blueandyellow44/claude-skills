#!/usr/bin/env python3
"""
Right build to the right site. PreToolUse on Bash.

Each production site deploys from its own branch with its own build. Before a
`wrangler pages deploy` to a known Pages project, this checks that the checkout
is on that site's branch and that the built page is a build FOR that site: its
og:url must be the site's URL, and a site's share card (if it has one) must be
in its own build and in no other site's build.

Sites: wallywalks.app below. A project with more than one site adds the others
in a JSON file named by CITY_WALKS_SITES, same shape as SITES, for example
  {"other-project": {"url": "https://other.example", "branch": "other",
                     "build": "npm run build:other", "card": "/og/other.png"}}
Entries there are added to, and replace, the built-in ones.

MEASURED LIMITS: it reads the command text. It sees `wrangler pages deploy
<dir>` with --project-name, after an optional `cd <dir> &&`. It cannot see a
deploy started from inside a script (scripts/deploy-site.mjs runs the same
check itself) or a project named some other way. Silent for every other
command and project.

Reads the hook JSON on stdin. Blocks with exit 2 and the reason on stderr.
"""
import json, os, re, shlex, subprocess, sys

SITES = {
    "wallywalks-app": {"url": "https://wallywalks.app", "build": "npm run build", "branch": "wallywalks-app", "card": None},
}


def block(msg):
    print(f"site_guard: {msg}", file=sys.stderr)
    sys.exit(2)


def sites():
    out = dict(SITES)
    path = os.environ.get("CITY_WALKS_SITES")
    if path:
        try:
            out.update(json.load(open(os.path.expanduser(path))))
        except (OSError, ValueError) as e:
            block(f"CITY_WALKS_SITES={path} could not be read ({type(e).__name__}); fix it or unset it")
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not re.search(r"wrangler\s+pages\s+deploy\b", cmd):
        return
    # The deploy segment, and any `cd` that ran before it in the same command.
    segments = re.split(r"&&|;|\|\|", cmd)
    cwd = data.get("cwd") or os.getcwd()
    target = None
    for seg in segments:
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        if len(words) >= 2 and words[0] == "cd":
            cwd = os.path.join(cwd, os.path.expanduser(words[1]))
            continue
        if "pages" in words and "deploy" in words:
            target = words
            break
    if not target:
        return
    project = None
    for i, w in enumerate(target):
        if w == "--project-name" and i + 1 < len(target):
            project = target[i + 1]
        elif w.startswith("--project-name="):
            project = w.split("=", 1)[1]
    known = sites()
    site = known.get(project or "")
    if not site:
        return
    try:
        branch = subprocess.run(["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        branch = ""
    if branch and branch != site["branch"]:
        block(f"{project} deploys only from branch {site['branch']}; this checkout is on {branch}")
    after = target[target.index("deploy") + 1:]
    out_dir = next((w for w in after if not w.startswith("-")), "out")
    page = os.path.join(cwd, out_dir, "index.html")
    if not os.path.isfile(page):
        block(f"no built page at {page}; build first ({site['build']}) before deploying to {project}")
    html = open(page, encoding="utf-8", errors="replace").read()
    og = re.search(r'property="og:url" content="([^"]+)"', html)
    og_url = og.group(1) if og else None
    own_card = site.get("card")
    foreign = [p for p, s in known.items() if p != project and s.get("card") and s["card"] in html]
    if og_url != site["url"] or (own_card and own_card not in html) or foreign:
        block(
            f"{out_dir}/index.html is a build for {og_url or 'an unknown site'}"
            f"{' carrying the share card of ' + ', '.join(foreign) if foreign else ''}, not for {project} ({site['url']}). "
            f"Rebuild with `{site['build']}`, or use scripts/deploy-site.mjs."
        )


if __name__ == "__main__":
    main()
