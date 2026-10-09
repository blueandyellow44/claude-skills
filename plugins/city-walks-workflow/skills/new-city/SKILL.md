---
name: new-city
description: "Stand up a new hand-drawn walking-map city on the City Walks Template pipeline: nine gated stages, one overlay file, a human's word required at three points. Runs inside a checkout of the City Walks Template repo."
---

# Standing up a new city

This repo builds one city at a time from `city/<id>/city.json`. Read
`city/README.md` and `docs/city-lessons.md` before touching anything. The
lessons file is the reason every gate exists, and a gate that seems
over-strict almost certainly traces to a real failure recorded there.

## The standing rule

**A failing gate is fixed at the data, never by loosening the gate.** If a
gate is genuinely wrong for a case it wasn't designed for, that's a real
finding: stop, explain the case, and let the human decide whether to change
the gate. Do not edit `scripts/city/gates.mjs` to make a red check green
without that conversation happening first. This mirrors the project's
standing engineering rule (find root causes, no quiet rollbacks) applied to
this specific pipeline.

## Sequence

```bash
npm run city -- status                 # where does this city stand right now
npm run city -- run <stage>            # print that stage's recipe before doing it
# ... do the stage's steps ...
npm run city -- gate <stage>           # check the evidence
```

Stages run in order: `init → research → places → photos → basemap → walks →
plates → prompts → ship`. Don't skip ahead: `places` depends on `research`'s
dossier for its worked examples, `prompts` depends on `places` existing at
all, and so on. `npm run city -- status` shows what's passed.

A gate reports one of three states, and they mean different things:

- **PASS**: checked, and it's right.
- **FAIL**: checked, and it's wrong. Fix the data (or the code that produces
  it), never the gate.
- **SKIP**: the check couldn't run yet (usually: the stage hasn't started).
  A SKIP is not a pass. Never report a stage "done" on the strength of a SKIP.

## Which steps are agent-run vs. gated on a human's word

Every stage's recipe (`npm run city -- run <stage>`) tags each step `[free]`,
`[PAID]`, or `[GATED ON MAX]`. Free steps you should just run. PAID steps
(research agents, geocoding sweeps, image generation) are printed, never
fired automatically by the CLI. Spend money deliberately, once, having
looked at what the step actually does.

Three points are hard-gated on the human's explicit word, not just "paid":

1. **Art direction** (basemap stage). Concept images go in front of the
   human; `art-direction/DECISION.md` records which one won and why, and
   must exist *before* any styled-render code runs. The `gate basemap` check
   enforces the ordering by file mtime; see `lock-art-direction-first` in
   the lessons ledger for why this is non-negotiable rather than a
   nice-to-have.
2. **Ship / deploy.** The `gate ship` check for deploy always reports SKIP:
   that's deliberate, not a bug in the gate. Deploying is a separate,
   explicit approval every time, never bundled with "the build works
   locally." See `deploy-on-max-word` in the lessons ledger.
3. **Anything the schema marks provisional.** Landmark GPS anchors start
   `provisional: true` in `city.json` and the basemap gate refuses to pass
   while any remain. Verify against OSM, record a `source`, then flip it.
   Don't flip it on memory or a plausible guess.

## When a stage's real work isn't code

`research`, `places` (partially), `photos` (partially), and `prompts`'
worked-example authoring lean on agents doing open-ended work: research
agents, geocode-verification sweeps, a human reading six generated field
notes for register. The gate checks what's checkable (sourcing, bounds,
coverage counts, key-placeholder hygiene) and explicitly cannot judge taste.
Where the recipe says "human read gate," that step is not optional just
because the deterministic checks passed.

## If something about the pipeline itself needs to change

That's not a new-city task, it's a kit task. Stop, explain what's missing or
wrong (a gate with no lesson behind it, a stage that doesn't fit a city's
shape; Bend's landlocked flat2d lane vs. SF's charcoal lane already show the
kit has real branches), and let the human decide whether it's a per-city
override in `city.json` (extend the schema) or a pipeline change. Don't
special-case a city by hand-editing a generated file; see
`generated-never-hand-edited`.
