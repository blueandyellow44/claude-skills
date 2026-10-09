# Claude Skills

Skills I use in Claude Code and Claude Cowork, packaged as an installable marketplace. Most of these started as tools I built for my own work and then cleaned up to share.

## Install

    /plugin marketplace add blueandyellow44/claude-skills
    /plugin install writing-toolkit@sheahan-skills

Then run a skill. Plugin skills are namespaced by their plugin, so `draft-critic` becomes `/writing-toolkit:draft-critic`.

## What is inside

| Plugin | Skills | For |
| --- | --- | --- |
| `writing-toolkit` | `draft-critic` | Finding what makes a nonfiction draft read as generated |
| `voice-toolkit` | `voice-corpus-extractor`, `voice-profile-builder`, `voice-profile-iteration` | Capturing and reproducing a writing voice |
| `document-toolkit` | `dossier`, `polished-pdf` | Researching a person into a brief, and laying out designed PDFs |
| `secure-core` | `secure-launch`, `security-inventory`, `launch-security-audit` | Mapping a repo's attack surface and running the whole security suite into one ledger |
| `secure-secrets` | `secret-scan`, `transcript-secret-guard`, `secret-rotation` | Keeping key values out of repos and saved sessions, and rotating them |
| `secure-supply-chain` | `dependency-audit`, `built-code-load-check` | Dependency risk without automatic upgrades |
| `secure-app` | `asvs-lite`, `abuse-and-spend`, `outbound-fetch-guard`, `mutation-proven-tests` | App-layer holes, open proxies, and paid APIs with no spending cap |
| `secure-platform` | `cloudflare-pages-workers`, `nextjs-opennext`, `fly-supabase`, `google-apps-script`, `railway` | Platform settings, one adapter per host |
| `secure-gate` | `secure-gate` | Refusing a launch while any check is failing or unknown |
| `city-walks-workflow` | 15 skills, from `landmark-piece` to `dual-site-deploy` | The working kit behind the illustrated Wally Walks map |

### writing-toolkit

`draft-critic` reads a newsletter, essay, post, or memo and finds the tells: the sentence that explains what the example already showed, the abstraction standing where a specific belongs, the rhythm that never changes, the paragraphs that keep landing on a neat verdict. A stdlib Python script counts what can be counted first, then the skill grades six dimensions and returns a quoted, line-by-line flag list. It never rewrites, and it never invents an example to make a line more concrete.

### voice-toolkit

Three stages, in order.

`voice-corpus-extractor` is the deterministic front end. Point it at a folder of speaker-attributed sources, scripts, transcripts, plays, or prose, and it pulls one speaker's complete cited corpus with countable metrics: turn-length distribution, short-turn share, aria frequency. It counts and it does not interpret.

`voice-profile-builder` turns that corpus into a profile. Core traits, anti-rules, register variants, a lexicon, and a calibration set, with every trait carrying a real quote. No quote, no trait.

`voice-profile-iteration` hardens an existing profile by writing one original example per register, having you grade each, and iterating until the set locks. It proves the profile generates the voice rather than merely describing it.

The design rule underneath all three is that nothing grades its own output. The extractor counts, the builder interprets, and a human closes the calibration gate.

### document-toolkit

`dossier` researches a real person before a meeting, interview, or sales call and builds a short PDF brief in their organization's colors. Every fact carries its source, single-source claims are flagged, and thin results are reported as thin rather than padded.

`polished-pdf` lays out reports, letters, and planning documents as HTML and renders them to PDF through headless Chrome. It can match an organization's brand from its site or brand guide, or offer directions from an aesthetic library, and it checks every rendered page before handing the file over. `dossier` uses its renderer.

### Secure Launch (six plugins)

A security pass to run before a site goes live. `secure-core` is the front door and every other `secure-*` plugin needs it, so install it first:

    /plugin install secure-core@sheahan-skills

Then add the plugins for what you ship. `/secure-launch` maps the attack surface, runs every check that applies, and writes one findings ledger. Each check reports PASS, FAIL, or UNKNOWN with its evidence. UNKNOWN is never folded into a pass: it means the check could not run, and the ledger says why. Every check has been seen to FAIL on a planted bad case before it is allowed to PASS, and the scripts never print a secret value.

`secure-gate` turns the ledger into a gate (a GitHub Actions workflow, a deploy-script check, or a pre-push hook) that refuses while anything is failing, or unknown and not accepted by the owner with a reason and a date.

Each plugin carries its own tests: `bash plugins/<plugin>/tests/run_tests.sh`. The checks use `gitleaks` and `npm` where they need them and report UNKNOWN when either is missing.

### city-walks-workflow

The skills behind [wallywalks.app](https://wallywalks.app), an illustrated walking-tour map. They cover drawing a landmark piece from its survey, reviewing each piece against evidence before it lands, drawing a real person as a sprite, walk cycles and walker motion, repairing and preflighting the map, a preview deploy, deploying two sites from their own branches, a Google sign-in checklist for Pages, keeping one shared Chrome, and setting up a new city. Two hooks act as tripwires on map pieces and on deploys.

They are written for that app's layout, so most of them are a pattern to adapt rather than a drop-in. Point them at your repo with `CITY_WALKS_REPO`; with it unset, the hooks stay silent.

## Notes

These are practitioner tools, not a framework. They assume Claude Code or Claude Cowork. If one is useful to you, take it and adapt it.

## License

MIT
