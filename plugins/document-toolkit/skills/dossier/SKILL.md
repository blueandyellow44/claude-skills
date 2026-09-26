---
name: dossier
description: >
  Research a real person and produce a polished PDF dossier for meeting prep,
  job-application research, competitor/peer analysis, or consulting client
  research. Pulls from web search, the subject's org site (brand colors +
  context), and any notes the user already has; outputs a brand-adapted PDF via
  an HTML-to-PDF render, in a quick (2-3 pp) or deep (5-8 pp) tier. The
  output should feel hand-prepared by a sharp consultant, not generated from a
  template. Use when the user says "dossier on [name]", "research [name]", "prep
  me for [name]", "who is [name]", "build a file on [name]", "background on
  [name]", or "meeting prep for [name]", or names a hiring manager, interviewer,
  competitor, or client to understand before an interaction. This is for a REAL
  person, for a fictional character profile use character-dossier instead.
---

# Dossier Skill

## Purpose

Research a specific person and assemble structured, actionable intelligence
into a polished PDF. The output should feel like something a sharp consultant
prepared by hand, not something an AI generated from a template.

Every dossier answers one question: **What do I need to know about this person
to walk into a room and be effective?**

---

## Invocation

The user must specify:

1. **Who**: Name and enough context to disambiguate (org, role, city)
2. **Why**: The use case, meeting prep, job app, competitor analysis, or consulting
3. **Depth**: `quick` or `deep`

If the user does not specify depth, ask:

> Quick or deep? Quick gets you the key facts in 2-3 pages. Deep runs full
> research, org context, landmines, conversation hooks, recommended approach
>, and produces 5-8 pages.

If the user does not specify the use case, infer from context. If ambiguous, ask.

---

## Expert decisions (the non-obvious calls)

Most of the pipeline below is ordinary research. These are the judgments that separate a dossier that
feels hand-prepared by a sharp consultant from one that reads like an AI template, make them deliberately.

- **Thin results are signal, not failure.** A subject with almost no web presence is itself intel (private
  by choice, junior, or operating under another name). Report the thinness honestly and stop; do not pad to
  a page count. A 2-page dossier of solid facts beats a 5-page one of inference.
- **Single-source facts are flagged, never laundered.** Anything appearing in exactly one source goes into
  Source Notes marked single-source. If the user repeats a wrong fact in the room because you presented an
  unverified claim as established, the dossier has failed at its one job.
- **Forced rapport is worse than none.** Manufactured "shared interests" are transparent and cost
  credibility. If there is no genuine hook, say so, a real cold open beats a fake warm one.
- **Brand color, adapted not copied.** Pull the org's primary/dark/accent; keep background, text, and
  borders FIXED warm neutrals so the document stays readable regardless of the brand. Darken a too-light
  primary, lighten a near-black one, desaturate garish/high-saturation brands 20-30%. NEVER ship the
  default midnight-navy / ice-blue palette: it is the single clearest "an AI made this" tell.
- **Motivations are reported, not assumed.** State what the subject has publicly said and done; never assert
  what they privately want. Contradictions between sources are surfaced, not smoothed.

### Use-case judgment calls (the non-obvious ones)
- **Hiring-manager research:** NEVER infer interview style from title alone, a "Director" at a 30-person
  startup interviews nothing like one at a Fortune 500. Read their actual writing/talks for structured-vs-
  conversational and technical-vs-behavioral signals; if there is no signal, mark it unknown rather than guess.
- **Consulting-client research:** budget and authority are almost always inferred (funding round, headcount
  growth, recent tooling spend, who they thank publicly). Present them as inference with the signal named ,
  never state "their budget is X" or "they decide" as fact, because a wrong authority read wastes the meeting
  on the wrong person.
- **Competitor/peer analysis:** position them relative to the USER, not in the abstract. A generic market map
  is not intel; the value is the specific overlap, the gap the user can exploit, and what the user can take
  from their approach.
- **Recency beats prominence.** A six-month-old role change, reorg, or stated priority outranks a famous fact
  from five years ago, people walk in briefed on the subject's past and miss what changed last quarter.

---

## Research Pipeline

Execute these steps in order. Do not skip steps. Do not start building the
document until research is complete.

### Step 1: Web Search, The Person

Run 3-5 searches depending on depth tier. Every search query should be short
and specific (1-6 words).

**Quick tier (3 searches minimum):**
```
[Name] [Organization]
[Name] [Role/Title]
[Name] LinkedIn background
```

**Deep tier (5-8 searches minimum):**
```
[Name] [Organization]
[Name] [Role/Title]
[Name] LinkedIn background
[Name] interview OR talk OR keynote OR podcast
[Name] [Organization] news [current year]
[Organization] leadership team
[Name] publications OR writing
[Name] controversy OR criticism  (only if relevant signals appear)
```

After each search, fetch the 1-2 most promising results to get full content.
Do not rely solely on search snippets.

### Step 2: Web Fetch, Org Website for Brand Colors

Fetch the subject's organization's homepage. Extract brand colors from:

- Logo colors visible in the header
- Primary navigation/header background color
- Accent colors used for buttons or CTAs
- Footer background color

**Goal:** Identify three colors for the dossier theme:

| Role | What to extract | Fallback |
|------|----------------|----------|
| Primary (dark) | Header/nav background, logo dominant color | `3D3935` (warm charcoal) |
| Secondary (medium) | Button/CTA color, accent color | `8C7B6B` (warm stone) |
| Accent (highlight) | Link color, hover state, secondary accent | `C4956A` (muted copper) |

If the org site cannot be reached or colors are unclear, use the **warm neutral
fallback palette** defined below.

**Color extraction method:**

Look at the fetched page content for:
- CSS in `<style>` tags or inline styles with hex/rgb values
- Brand-colored elements (headers, nav bars, buttons)
- Meta theme-color tag: `<meta name="theme-color" content="#...">`

You do not need to be pixel-perfect. Get close enough that the document
feels visually connected to the org without being a copy of their website.

### Step 3: Existing Notes Check

If a Google Drive, notes, or file-search tool is connected, check whether the
user already has notes, docs, or prior dossiers on this person. If none is
connected, ask the user once whether they have notes to share, then move on:

```
Search: [Person's name]
Search: [Person's organization name]
```

If results are found, read them and incorporate any existing intel. Flag
what is new vs. what the user already had.

### Step 4: Compile and Cross-Reference

Before building the document:

1. List every fact you found with its source
2. Flag anything that appears in only one source and cannot be verified
3. Flag any contradictions between sources
4. Identify gaps, what you could not find that would be useful
5. Do not fabricate or infer facts that are not sourced

---

## Dossier Sections

### Section Map by Depth Tier

| # | Section | Quick | Deep | Notes |
|---|---------|-------|------|-------|
| 1 | Cover Page | ✓ | ✓ | Name, title, org, date, use case label |
| 2 | At a Glance | ✓ | ✓ | 5-7 bullet snapshot of key facts |
| 3 | Background | ✓ | ✓ | Career arc, education, tenure |
| 4 | Current Role & Org Context | ✓ | ✓ | What they do, what the org does, where they sit |
| 5 | What They Care About | ✓ | ✓ | Stated priorities, public positions, themes in their work |
| 6 | Conversation Hooks | ✓ | ✓ | Shared interests, recent wins, rapport builders |
| 7 | Landmines & Sensitivities |, | ✓ | Controversies, org politics, public missteps, sore spots |
| 8 | Org Landscape |, | ✓ | Reporting structure, peers, org dynamics, recent changes |
| 9 | Recent Activity |, | ✓ | Talks, publications, news mentions, social media themes |
| 10 | Use-Case Intel |, | ✓ | Varies by use case (see below) |
| 11 | Recommended Approach |, | ✓ | How to frame your ask, what language to use, what to avoid |
| 12 | Source Notes | ✓ | ✓ | Where each key fact came from; gaps flagged |

## Reference loading

The bulk spec lives in references so this file stays scannable. Reading a reference means reading the whole
file. Load only the one the current step needs:

- **`references/section-details.md`**, full per-section writing guidance for sections 1-12 (purpose,
  format, and rules per section). Load when you START WRITING the document, after research is compiled. Do
  NOT load during research.
- **`references/visual-design.md`**, brand-color adaptation (the theme variables, the desaturation/lightness
  rules), the warm-neutral fallback palette, typography, and layout. Load at the BUILD step, when you start
  building the page. Do NOT load during research or content drafting.
- **`references/output-pipeline.md`**, the HTML -> PDF render and visual QA sequence, using the
  polished-pdf skill in this plugin. Load at the BUILD step, once the content is final.

Do NOT load all three up front; each is only needed at its own stage.

---

## Quality Gates

Before presenting the dossier to the user:

### Research Quality
- [ ] Every factual claim has a source
- [ ] Single-source claims are flagged in Source Notes
- [ ] No fabricated or inferred facts presented as established
- [ ] Gaps in research are explicitly acknowledged
- [ ] Existing notes were checked (connected tool or asked the user)
- [ ] Conversation hooks are based on real information, not manufactured

### Visual Quality
- [ ] Brand colors extracted and adapted (or fallback applied with note)
- [ ] Every rendered page inspected before delivery
- [ ] No text overflow, cut-off, or overlapping elements
- [ ] Body text is 12pt minimum, nothing below 10pt
- [ ] Cover page looks clean and intentional
- [ ] Document does not look like a generic AI template

### Content Quality
- [ ] At a Glance section is genuinely scannable in 30 seconds
- [ ] Background tells a story, not a resume list
- [ ] Conversation Hooks are specific and actionable
- [ ] Landmines section is factual, not speculative (deep only)
- [ ] Recommended Approach gives concrete guidance, not platitudes (deep only)
- [ ] Tone is that of a sharp colleague briefing you, not a research report

---

## Handling Thin Results

Some subjects will have a thin web presence. This is information, not a failure.

If research yields limited results:

1. **Say so explicitly.** "Limited public information available on [Name]. Here
   is what I found."
2. **Do not pad the dossier with filler.** A 2-page dossier with solid facts
   is better than a 5-page dossier with speculation.
3. **Flag what is missing.** "Could not find: education background, previous
   roles before [Org], public statements on priorities."
4. **Suggest next steps.** "You may want to check LinkedIn directly or ask
   [mutual contact] for background."
5. **In quick mode with thin results**, the output may be a single well-designed
   page. That is fine.

---

## Anti-Patterns

| Anti-Pattern | Why It Is Wrong | Do This Instead |
|---|---|---|
| Fabricating conversation hooks | Forced rapport is transparent and cringe | Say "no obvious shared interests found" |
| Padding with generic advice | "Be a good listener" is not intel | Give specific, sourced guidance or skip the section |
| Assuming motivations | You do not know what someone privately wants | Report what they have publicly said and done |
| Repeating the same fact in multiple sections | Feels like padding | State each fact once in its most relevant section |
| Using the midnight navy / ice blue palette | It screams "AI made this" | Extract brand colors or use warm neutral fallback |
| Ignoring contradictions in sources | Destroys credibility if the user cites a wrong fact | Flag contradictions explicitly |
| Treating thin results as failure | Low profile is useful signal in itself | Report it honestly with suggested next steps |

---

## Example Invocations

```
"Dossier on Sarah Chen, VP of Product at Amplify Education. Deep. Meeting prep."

"Quick dossier on James Rodriguez, he's the hiring manager for the PM role
at MagicSchool AI."

"Build a file on Dr. Kenji Tanaka. He runs the AI in Education lab at Stanford.
Competitor/peer analysis. Deep."

"Prep me for a call with Rachel Wu. She's the CEO of a K-8 tutoring startup
called BrightPath. Consulting client. Deep."
```

