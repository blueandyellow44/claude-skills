# city-walks-workflow

Skills and two gates for building a hand-drawn walking map, as used on the SF City Walks map at wallywalks.app. Most of them exist because something went wrong on the real map at least once; where a skill has a "Why this exists" section, it says what.

| Skill | Cause it fixes |
|---|---|
| landmark-piece | The image model misshapes a building; a survey render broke the one camera |
| piece-review | Pieces were checked at one zoom only; nothing enforced the check |
| map-character | Drawing a real person as a map sprite took four rounds |
| walk-cycle | An animated walker needs frames that stay on one baseline and one ink color |
| walker-motion | The walker drifted against the street, walked in place, or faced the wrong way |
| map-repair | Map defects fixed one way each: mask-only repaints, roads in the map's hand, the loop on the road, pieces as sharp overlays, super-resolution |
| map-preflight | An outside audit found 17 defects nothing in the build caught; a script plus named looks finds them first |
| new-city | Standing up a new city on the City Walks Template pipeline, one gated stage at a time |
| address-index | Address autocomplete from the city's own address table, no Places API |
| shared-chrome | Several sessions share one Chrome; hidden pages stall |
| pages-preview | The preview deploy and its two caches lived in one session's memory |
| dual-site-deploy | Each production site must deploy from its own branch with its own build |
| cross-session-port | Moving commits onto a branch another session owns, without touching its tree |
| google-signin-pages | The sign-in setup was done once, by hand, in a console |
| linkedin-carousel | Browser screenshots made blurry slides; the carousel is drawn in code |

## Setup

Set `CITY_WALKS_REPO` to the map app's checkout. The hooks act only inside that folder and are silent everywhere when it is unset. The scripts take `--repo` too.

Scripts are Python 3 with Pillow and numpy (map-preflight also uses OpenCV). Shared helpers: `lib/cw_common.py`.

## Hooks

`hooks/hooks.json` holds tripwires, not containment.

- `piece_gate.py pre` blocks a command or edit that names a sprite (or a sprite script, a whole-set re-key, or a git command that restores sprites) until an object record under 12 hours old exists with its brief written. A script that writes a sprite without naming its path is outside it.
- `piece_gate.py stop` blocks a reply that calls a piece fixed until review evidence exists that is well formed, recent and bound to the sprite's bytes. It matches English phrasing, so it can miss a claim or block a sentence that only sounds like one, and it lets go after two blocks with a NOT RESOLVED warning.
- `site_guard.py` blocks a `wrangler pages deploy` from the wrong branch, or of a build made for another site. Sites beyond wallywalks.app go in a JSON file named by `CITY_WALKS_SITES` (format at the top of the script).

Neither piece gate proves that a record was read or a capture was looked at. Measured cases: `tests/`.

## Object records

The piece gate wants a record of a piece's history before its sprite changes: `<repo>/.agents/object-records/<slug>-<YYYYMMDD>.md`. A record counts when it has

- a `generated: <ISO time>` line, under 12 hours old;
- the headings `## 1. git history`, `## 4. written rulings`, `## 5. <whose> own words` and `## 6. Brief`;
- under `## 6. Brief`, four `- label: answer` lines with distinct written answers: who decided what and when, what was rejected, the approved version, and what the planned change touches.

Write it by hand or with your own generator. A whole-set change needs `<repo>/.agents/object-records/WHOLE-SET-<YYYYMMDD>.md` quoting the owner's word for it.

## Tests

Each test in `tests/` takes the script under test as its argument, for example `python3 tests/hook_cases.py hooks/piece_gate.py`, and needs `CITY_WALKS_REPO` set. They use fixtures and mocks and change nothing in the repo. `camera_cases.py`, `weight_cases.py` and `return_path_case.py` read the app repo's own sprites, evidence files and API routes, so they run only against that repo.

Editing an installed copy does not change what a running session loads: Claude Code runs the copy in its plugin cache until the plugin is updated or reinstalled.
