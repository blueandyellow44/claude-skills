"""Hook payloads sent as JSON on stdin. Nothing here is executed against the repo."""
import json, os, subprocess, sys
R = os.environ.get("CITY_WALKS_REPO") or sys.exit("set CITY_WALKS_REPO to the map repo")
hook = sys.argv[1]
B = lambda cmd, cwd=R: ("pre", {"cwd": cwd, "tool_name": "Bash", "tool_input": {"command": cmd}})
W = lambda path, tool="Write", cwd=R: ("pre", {"cwd": cwd, "tool_name": tool, "tool_input": {"file_path": path}})
S = lambda msg, cwd=R, **k: ("stop", dict({"cwd": cwd, "last_assistant_message": msg, "session_id": "t-" + str(abs(hash(msg)) % 10**6)}, **k))
SP = "public/images/sprites/sf"
cases = [
 # (label, want exit, payload)  -- BYPASSES: must block (2)
 ("python one-liner writes sprite", 2, B(f"python3 -c \"from PIL import Image; Image.new('RGBA',(9,9)).save('{SP}/coit-tower.png')\"")),
 ("node one-liner writes sprite", 2, B(f"node -e \"require('fs').writeFileSync('{SP}/coit-tower.png', Buffer.alloc(9))\"")),
 ("heredoc writes sprite", 2, B(f"python3 - <<'PY'\nopen('{SP}/coit-tower.png','wb').write(b'x')\nPY")),
 ("git checkout sha -- sprite", 2, B(f"git checkout b5b0b26 -- {SP}/ferry-building.png")),
 ("git checkout sha -- sprite dir", 2, B(f"git checkout b5b0b26 -- {SP}")),
 ("git stash pop, stash holds no sprite (repo has no stash)", 0, B("git stash pop")),
 ("unnamed sprite script", 2, B("python3 scripts/sprites/ink-occupancy.py")),
 ("cat; cp onto sprite", 2, B(f"cat notes.txt; cp /tmp/x.png {SP}/coit-tower.png")),
 ("ls; rm sprite", 2, B(f"ls; rm {SP}/coit-tower.png")),
 ("destructive cp with '# git' comment", 2, B(f"cp /tmp/x.png {SP}/coit-tower.png # git")),
 ("raw sprite path write", 2, B("cp /tmp/x.png .tmp/sprites/sf-poster/raw-sf/coit-tower.png")),
 ("../ normalized path", 2, B(f"cp /tmp/x.png components/../{SP}/coit-tower.png")),
 ("Write tool, ../ path", 2, W(f"{R}/components/../{SP}/coit-tower.png")),
 ("Write tool to raw dir", 2, W(f"{R}/.tmp/sprites/sf-poster/raw-sf/coit-tower.png")),
 ("Write to repo sprite from other cwd", 2, W(f"{R}/{SP}/coit-tower.png", cwd=os.path.expanduser("~"))),
 ("whole-set re-key", 2, B("npm run sprites:key")),
 # must pass (0)
 ("sibling repo prefix (<repo>-2)", 0, B(f"cp /tmp/x.png {SP}/coit-tower.png", cwd=R + "-2")),
 ("git log on sprite", 0, B(f"git log --all -- {SP}/de-young.png")),
 ("git show sprite to scratch", 0, B(f"git show c3b44f7:{SP}/ferry-building.png > /tmp/f.png")),
 ("shasum sprite", 0, B(f"shasum -a 256 {SP}/ferry-building.png")),
 ("npm run build", 0, B("npm run build")),
 ("unrelated edit", 0, W(f"{R}/components/LiveMap.tsx", tool="Edit")),
 # STOP: escaped claims, must block (2)
 ("'is ready'", 2, S("The de Young piece is ready.")),
 ("split sentences", 2, S("I redrew the Legion of Honor. It is fixed now.")),
 ("pronoun", 2, S("About the Cliff House sprite: it now faces the ocean and looks right.")),
 ("unrelated hedge same sentence", 2, S("The Ferry Building is fixed, though the sign-in page is not yet verified.")),
 ("plain known-bad", 2, S("The de Young is fixed: drawn from its survey.")),
 # STOP: false blocks, must pass (0)
 ("historical restored Ferry", 0, S("The hub records that the Ferry Building was restored on 2026-10-03 to the c3b44f7 piece.")),
 ("Oracle docs", 0, S("Fixed the sign-in bug; the Oracle docs confirm the cookie flags.")),
 ("Grace login", 0, S("Grace's login is fixed and verified on test.")),
 ("honest hedge", 0, S("The de Young is redrawn but not yet verified at full zoom-out.")),
 ("no piece", 0, S("Fixed the redirect; /api/me returns the session.")),
 ("other repo", 0, S("The de Young is fixed.", cwd=os.path.expanduser("~"))),
]
bad = 0
for label, want, (mode, payload) in cases:
    p = subprocess.run([sys.executable, hook, mode], input=json.dumps(payload), capture_output=True, text=True)
    ok = p.returncode == want
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} want {want} got {p.returncode}  {label}")
print(f"\n{len(cases)} cases, {bad} wrong")
