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

## Notes

These are practitioner tools, not a framework. They assume Claude Code or Claude Cowork. If one is useful to you, take it and adapt it.

## License

MIT
