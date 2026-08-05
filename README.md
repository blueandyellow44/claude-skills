# Claude Skills

Skills I use in Claude Code and Claude Cowork, packaged as an installable marketplace. Most of these started as tools I built for my own work and then cleaned up to share.

## Install

    /plugin marketplace add blueandyellow44/claude-skills
    /plugin install skill-toolkit@sheahan-skills

Then run a skill. Plugin skills are namespaced by their plugin, so `skill-judge` becomes `/skill-toolkit:skill-judge`.

## What is inside

| Plugin | Skills | For |
| --- | --- | --- |
| `skill-toolkit` | `process-interviewer`, `skill-judge` | Planning a build, and reviewing Claude skills |
| `voice-toolkit` | `voice-corpus-extractor`, `voice-profile-builder`, `voice-profile-iteration` | Capturing and reproducing a writing voice |

### skill-toolkit

`process-interviewer` refuses to let you start building until the plan is unambiguous. It interviews you across four phases, hunts the gaps you did not know were there, and stress-tests the plan you thought was finished. Use it before anything complex, especially when you feel confident.

`skill-judge` scores a `SKILL.md` against eight design dimensions on a 120-point scale and returns a grade, an expert-to-activation knowledge ratio, an anti-pattern diagnosis, and ranked fixes. It judges; it does not rewrite.

### voice-toolkit

Three stages, in order.

`voice-corpus-extractor` is the deterministic front end. Point it at a folder of speaker-attributed sources, scripts, transcripts, plays, or prose, and it pulls one speaker's complete cited corpus with countable metrics: turn-length distribution, short-turn share, aria frequency. It counts and it does not interpret.

`voice-profile-builder` turns that corpus into a profile. Core traits, anti-rules, register variants, a lexicon, and a calibration set, with every trait carrying a real quote. No quote, no trait.

`voice-profile-iteration` hardens an existing profile by writing one original example per register, having you grade each, and iterating until the set locks. It proves the profile generates the voice rather than merely describing it.

The design rule underneath all three is that nothing grades its own output. The extractor counts, the builder interprets, and a human closes the calibration gate.

## Notes

These are practitioner tools, not a framework. They assume Claude Code or Claude Cowork. If one is useful to you, take it and adapt it.

## License

MIT
