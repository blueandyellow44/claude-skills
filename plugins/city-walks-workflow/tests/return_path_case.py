"""The sign-in return path must stay on the site. Runs the REAL safeReturn, copied
out of functions/api/[[route]].ts at run time, through WHATWG URL resolution (node).
History: until 2026-10-04 the predicate (starts with "/" and not "//") accepted
"/\\example.invalid", which browsers resolve to another origin: an open redirect
after sign-in. Fixed in the working tree 2026-10-04 on the owner's word. This test says
nothing about what is DEPLOYED; check the live site separately."""
import json, os, re, subprocess, sys
REPO = os.environ.get("CITY_WALKS_REPO") or sys.exit("set CITY_WALKS_REPO to the map repo")
src = open(os.path.join(REPO, "functions/api/[[route]].ts"), encoding="utf-8").read()
m = re.search(r"const safeReturn = \(p: string \| undefined\)(?:: string)? => (\{.*?\n\};|\(.*?\);)", src, re.S)
if not m:
    print("safeReturn NOT FOUND in the app (it changed shape); re-read the file. Result: UNKNOWN"); sys.exit(3)
fn = "const safeReturn = (p) => " + m.group(1)
cases = {"/\\example.invalid": "/", "/\\/example.invalid": "/", "//example.invalid": "/", "https://example.invalid": "/",
         "/\t/example.invalid": "/", "": "/", "/": "/", "/walks": "/walks", "/?walk=abc": "/?walk=abc", "/privacy#top": "/privacy#top"}
js = fn + "\nconst cases=" + json.dumps(cases) + """;let bad=0;
for (const [i,w] of Object.entries(cases)) { const g=safeReturn(i); const o=new URL(g,'https://wallywalks.app').origin;
  const ok = g===w && o==='https://wallywalks.app'; if(!ok) bad++; console.log((ok?'ok   ':'FAIL ')+JSON.stringify(i)+' -> '+JSON.stringify(g)+' ('+o+')'); }
if (safeReturn(undefined)!=='/') { bad++; console.log('FAIL undefined'); }
console.log('\\n'+(Object.keys(cases).length+1)+' cases, '+bad+' wrong. Same-site guarantee '+(bad?'UNMET':'holds')+' in the working tree.'); process.exit(bad?1:0);"""
p = subprocess.run(["node", "-e", js], capture_output=True, text=True)
print(p.stdout.strip() or p.stderr.strip()); sys.exit(p.returncode)
