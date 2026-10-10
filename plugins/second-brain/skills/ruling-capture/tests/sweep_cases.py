"""Decoys for the ruling sweep: scratch hub + scratch transcript. Pass the sweep script path."""
import json, os, subprocess, sys, tempfile
sweep = sys.argv[1]
d = tempfile.mkdtemp(prefix="sweep-")
hub = os.path.join(d, "hub.md")
open(hub, "w").write("""# Rules
- **The dashboard opens on the whole year (owner, "the opening must always show the whole year on every screen").**
- The compass: REMOVE it. The owner's earlier ask "I want a violet compass icon on every route" was reversed; no compass icon.
- Sign-in: people log in before they can add a report, browsing stays open and i want that kept.
""")
msgs = ["the opening must always show the whole year on every screen",          # verbatim in hub
        "they need to login to add a report seems like a good line, never for browsing",  # paraphrased in hub
        "labels must never overlap the trend line when a report is open",        # absent
        "I want a violet compass icon on every route",                           # quoted in a line that REMOVES it
        "approved",                                                              # a permission, not a rule
        "browsing stays open and i want the sample reports to always load without any login at all"]  # shares a run with the hub, says more
tr = os.path.join(d, "s1.jsonl")
with open(tr, "w") as f:
    for i, m in enumerate(msgs):
        f.write(json.dumps({"type": "user", "timestamp": f"2026-10-04T10:0{i}:00Z", "promptSource": "typed", "message": {"content": m}}) + "\n")
    f.write(json.dumps({"type": "user", "timestamp": "2026-10-04T10:09:00Z", "promptSource": "typed", "message": {"content": "the owner's direct correction: tabs must always open in the same browser"}}) + "\n")
out = subprocess.run([sys.executable, sweep, "--hub", hub, "--no-memory", "--transcripts", tr, "--show-exact"], capture_output=True, text=True).stdout
def bucket(m):
    cur = None
    for ln in out.splitlines():
        if ln.startswith("## "): cur = ln.split(":")[0][3:]
        if m[:40] in ln and ln.startswith("- "): return cur
want = ["EXACT", "ABSENT", "ABSENT", "CONTRADICTED", "PERMISSION", "PARTIAL"]   # a paraphrase shares no five-word run: ABSENT by design
bad = 0
for m, w in zip(msgs, want):
    got = bucket(m); bad += got != w; print(f"{'ok  ' if got == w else 'FAIL'} {w:12} got {got}: {m[:60]}")
got = bucket("the owner's direct correction"); bad += got != "UNCERTAIN"; print(f"{'ok  ' if got == 'UNCERTAIN' else 'FAIL'} UNCERTAIN    got {got}: relay in the third person")
print(f"\n7 cases, {bad} wrong"); sys.exit(1 if bad else 0)
