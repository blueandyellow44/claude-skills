"""Validate the ```base blocks in a note against Obsidian's Bases parser rules.

    python3 check_base_syntax.py [path/to/Home.md]

Defaults to this skill's own references/home.md.tmpl template, so it doubles as an
authoring pre-flight and as a post-scaffold check against the real vault.

The rules enforced here were read out of Obsidian 1.12.7's shipped parser, not
out of the documentation, because the three failure modes that actually bite
generated files are all undocumented and two of them are SILENT:

  - a `properties` key without a `note.`/`file.`/`formula.` prefix is stored
    raw but looked up normalized, so displayName never applies. Obsidian's own
    published example has this bug.
  - `direction` must be uppercase ASC/DESC. Lowercase is dropped without an
    error, so the view renders unsorted rather than broken.
  - `limit` must be an int > 0. Zero is dropped the same silent way.

A view missing `type` or `name` DOES throw in Obsidian, so those are checked
too, but they are the easy class: you find out immediately.
"""

import os, re, sys, yaml

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home.md.tmpl")
SRC = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
text = open(SRC, encoding="utf-8").read()
print(f"checking {SRC}\n")
blocks = re.findall(r"```base\n(.*?)```", text, re.S)
print(f"found {len(blocks)} base block(s)\n")

errs = []
def check(cond, msg):
    if not cond: errs.append(msg)

for i, b in enumerate(blocks, 1):
    print(f"--- block {i} ---")
    try:
        d = yaml.safe_load(b)
    except Exception as e:
        errs.append(f"block {i}: YAML does not parse: {e}"); continue
    check(isinstance(d, dict), f"block {i}: top level must be a mapping")
    print("  yaml: OK")

    # top-level keys must be recognised or preserved; flag typos in known set
    known = {"views","filters","properties","formulas","summaries",
             "newItemFolder","newItemTemplate","display"}
    for k in d:
        if k not in known: print(f"  note: unrecognised top-level key '{k}' (preserved, not an error)")

    # properties keys must be normalised
    for k in (d.get("properties") or {}):
        check(k.startswith(("note.","file.","formula.")),
              f"block {i}: properties key '{k}' is not normalised -> displayName will silently not apply")
        inner = d["properties"][k]
        check(isinstance(inner, dict) and set(inner) <= {"displayName"},
              f"block {i}: properties['{k}'] may only contain displayName")
    print(f"  properties: {len(d.get('properties') or {})} key(s) checked")

    def check_filter(f, where):
        if isinstance(f, str): return
        if isinstance(f, dict):
            keys = set(f) & {"and","or","not"}
            check(len(f) == 1 and len(keys) == 1,
                  f"block {i}: filter at {where} must have EXACTLY one of and/or/not, got {sorted(f)}")
            for sub in next(iter(f.values()), []) or []:
                check_filter(sub, where)
        else:
            errs.append(f"block {i}: filter at {where} is neither string nor mapping")

    if "filters" in d: check_filter(d["filters"], "top level")

    views = d.get("views")
    check(isinstance(views, list) and views, f"block {i}: views must be a non-empty array")
    for v in views or []:
        check(isinstance(v.get("type"), str) and v["type"], f"block {i}: view missing required 'type'")
        check(isinstance(v.get("name"), str) and v["name"].strip(), f"block {i}: view missing required non-empty 'name'")
        check(v.get("type") in {"table","cards","list"},
              f"block {i}: view type '{v.get('type')}' is not core-registered (table/cards/list)")
        if "filters" in v: check_filter(v["filters"], f"view '{v.get('name')}'")
        if "limit" in v:
            check(isinstance(v["limit"], int) and v["limit"] > 0,
                  f"block {i}: limit must be an int > 0, got {v['limit']!r} (silently dropped otherwise)")
        if "order" in v: check(isinstance(v["order"], list), f"block {i}: order must be an array")
        for s in v.get("sort", []) or []:
            check(set(s) >= {"property","direction"}, f"block {i}: sort entry needs property+direction")
            check(s.get("direction") in {"ASC","DESC"},
                  f"block {i}: direction {s.get('direction')!r} must be UPPERCASE ASC/DESC (silently dropped otherwise)")
        print(f"  view '{v.get('name')}': type={v.get('type')} OK")

print()
if errs:
    print("INVALID:")
    for e in errs:
        print("  -", e)
    sys.exit(1)
if not blocks:
    # Not a pass. A note with no base blocks was not validated, and saying
    # "valid" here would report a clean result for work that never ran —
    # which is how a permanently-green check earns trust it has not got.
    print("NO BASE BLOCKS FOUND — nothing was validated.")
    print("Expected if this vault's Obsidian predates 1.9 and the blocks were")
    print("deliberately stripped. Unexpected anywhere else: check Home.md.")
    sys.exit(0)
print(f"{len(blocks)} BASE BLOCK(S) VALID against the 1.12.7 parser rules")
