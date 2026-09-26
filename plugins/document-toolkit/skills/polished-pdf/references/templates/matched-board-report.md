# Matched board report

A board-ready decision document that wears the owning organization's own brand. Read this file when Step 1 takes the **Match a brand** path and Step 2 locks a board report, board pack, investment memo, operating review or turnaround plan. The layout grammar here is deliberately neutral so the brand profile, not this template, supplies the personality.

Load `brand-matching.md` first. No token in this scaffold may be filled from anything except the confirmed brand profile.

## Who reads it and what they must do

- **Reader:** a board member or investor, reading on a laptop or printed before a meeting, looking for what is true, what is being decided, and what it will cost.
- **Verb:** approve, challenge, or ask for more before deciding.
- **Consequence for layout:** the answer comes first, every claim shows whether it is known or inferred, numbers are tabular and aligned, and nothing decorative competes with a decision.

## Content-block schema

| Block | Required | Notes |
|---|---|---|
| `title`, `subtitle`, `date`, `prepared_by`, `prepared_for` | yes | Cover |
| `answer_first` | yes | Three to six sentences: the situation, the core call, the ask of the board |
| `diagnosis[]` | yes | Findings, each with `claim`, `evidence` (source file and location), `status` of `known`, `inferred` or `needs-data` |
| `decisions[]` | yes | Each with `decision`, `rationale`, `tradeoff`, `owner`, `reversible` |
| `priorities[]` | yes | Ranked, with what is explicitly deprioritized |
| `plan_30_60_90` | yes | Three horizons, each with actions, owner, milestone |
| `metrics[]` | yes | `metric`, `baseline` with source, `target`, `by when`, `owner` |
| `risks[]` | yes | `risk`, `likelihood`, `impact`, `mitigation`, `trigger` |
| `next_actions[]` | yes | Next seven days, named owners |
| `open_questions[]` | no | What must be learned before a consequential decision |
| `appendix` | no | Source index, method notes, supporting tables and charts |

If `answer_first`, `diagnosis` or `decisions` is empty, Step 3 refuses to proceed.

## Evidence status chips

Every finding, metric baseline and risk carries one chip. The three states are drawn from the brand palette, never from traffic-light colors unless the brand uses them.

- `Known`: solid chip in ink on ground.
- `Inferred`: outlined chip in accent.
- `Needs data`: dashed outline in muted ink.

## HTML scaffold

Fill every `{{ }}` from the brand profile. Delete a rule rather than invent a value.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{ title }}</title>
<style>
  /* Fonts: embed supplied files as data URIs, or link Google Fonts; never rely on a silent fallback. */
  {{ font_face_css }}
  /* Paint the ground in @page too: body backgrounds do not reach the page margins in Chrome's print path. */
  @page { size: 8.5in 11in; margin: 0.7in 0.75in 0.8in; background: {{ color.ground }}; }
  @page :first { margin: 0; }
  :root {
    --ground: {{ color.ground }};
    --ink: {{ color.ink }};
    --ink-muted: {{ color.ink_muted }};
    --rule: {{ color.rule }};
    --accent: {{ color.accent }};
    --support: {{ color.support | default(color.ink_muted) }};
    --field: {{ color.dark_field | default(color.ink) }};
    --on-field: {{ color.on_dark | default(color.ground) }};
    --display: {{ type.display_stack }};
    --body: {{ type.body_stack }};
    --label: {{ type.label_stack }};
    --display-weight: {{ type.display_weight }};
    --emphasis-style: {{ type.emphasis }};      /* italic, or a weight, per the guide */
    --label-tracking: {{ type.label_tracking }};
    --label-case: {{ type.label_case }};
    --radius: {{ layout.radius | default('0') }};
  }
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  html, body { margin: 0; background: var(--ground); color: var(--ink); }
  body { font-family: var(--body); font-size: 10pt; line-height: 1.5; font-variant-numeric: tabular-nums lining-nums; }
  h1, h2, h3 { font-family: var(--display); font-weight: var(--display-weight); line-height: 1.08; margin: 0; text-wrap: balance; }
  em { font-style: var(--emphasis-style); }
  .label { font-family: var(--label); font-size: 7.5pt; letter-spacing: var(--label-tracking); text-transform: var(--label-case); color: var(--ink-muted); }

  .cover { height: 11in; background: var(--field); color: var(--on-field); padding: 0.9in 0.85in; display: grid; grid-template-rows: auto 1fr auto; page-break-after: always; }
  .cover .mark { height: 0.42in; }
  .cover > div:nth-child(2) { align-self: end; }
  .cover h1 { font-size: 40pt; max-width: 6.2in; }
  .cover .sub { font-family: var(--display); font-size: 15pt; font-style: var(--emphasis-style); opacity: .85; margin-top: 0.18in; max-width: 5.8in; }
  .cover .meta { display: flex; gap: 0.4in; border-top: 0.75pt solid currentColor; padding-top: 0.14in; margin-top: 0.5in; }
  .cover .meta .label { color: inherit; opacity: .8; }

  section { break-inside: auto; margin-bottom: 0.34in; }
  .head { break-inside: avoid; break-after: avoid; margin-bottom: 0.14in; }
  h2 { font-size: 22pt; margin-top: 0.06in; }
  h3 { font-size: 13pt; margin: 0.16in 0 0.05in; }
  p { margin: 0 0 0.1in; max-width: 6.4in; }

  .answer { border-top: 2pt solid var(--accent); padding-top: 0.16in; font-family: var(--display); font-size: 14.5pt; line-height: 1.38; }

  table { width: 100%; border-collapse: collapse; margin: 0.1in 0 0.16in; font-size: 8.8pt; }
  thead th { font-family: var(--label); font-weight: 500; font-size: 7pt; letter-spacing: var(--label-tracking); text-transform: var(--label-case); text-align: left; color: var(--ink-muted); border-bottom: 1pt solid var(--ink); padding: 0.05in 0.07in; }
  td { border-bottom: 0.5pt solid var(--rule); padding: 0.07in; vertical-align: top; }
  td.num, th.num { text-align: right; white-space: nowrap; }
  tr { break-inside: avoid; }

  .chip { display: inline-block; font-family: var(--label); font-size: 6.5pt; letter-spacing: var(--label-tracking); text-transform: var(--label-case); padding: 1.5pt 5pt; border-radius: var(--radius); white-space: nowrap; }
  .chip.known { background: var(--ink); color: var(--ground); }
  .chip.inferred { border: 0.75pt solid var(--accent); color: var(--accent); }
  .chip.needs { border: 0.75pt dashed var(--ink-muted); color: var(--ink-muted); }

  .horizons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.22in; }
  .horizon { border-top: 2pt solid var(--ink); padding-top: 0.1in; break-inside: avoid; }
  .horizon:first-child { border-top-color: var(--accent); }

  .tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.16in; margin: 0.12in 0; }
  .tile { border-top: 0.75pt solid var(--rule); padding-top: 0.08in; break-inside: avoid; }
  .tile .big { font-family: var(--display); font-size: 24pt; line-height: 1; }

  .decision { display: grid; grid-template-columns: 1.25in 1fr; gap: 0.2in; padding: 0.12in 0; border-top: 0.5pt solid var(--rule); break-inside: avoid; }
  .footer-note { font-size: 7.5pt; color: var(--ink-muted); }
</style>
</head>
<body>
<section class="cover">
  <img class="mark" src="{{ logo.on_dark_data_uri }}" alt="{{ owner }}">
  <div>
    <div class="label">{{ doc_label }}</div>
    <h1>{{ title }}</h1>
    <div class="sub">{{ subtitle }}</div>
  </div>
  <div class="meta">
    <div><div class="label">Prepared for</div>{{ prepared_for }}</div>
    <div><div class="label">Prepared by</div>{{ prepared_by }}</div>
    <div><div class="label">Date</div>{{ date }}</div>
  </div>
</section>
<!-- Sections in order: answer first, diagnosis, decisions, priorities, 30/60/90, metrics, risks, next actions, open questions, appendix. -->
</body>
</html>
```

## Render

```sh
python3 scripts/render_pdf.py draft.html report.pdf --expect-fonts "<display>,<body>,<label>" --ground "<ground hex>" --skip-ground-pages 1
```

The script waits for fonts, prints backgrounds, and fails when an expected font is missing, any page other than the skipped cover is off the ground color, or an em dash is present. Chrome prints variable fonts as unnamed Type3 fonts; the script counts those as present when the browser loaded the family. Then read every thumbnail.

## Hard rules

1. The brand profile supplies every color and font. No hue or face outside it.
2. The guide's own prohibitions override this template. If the guide says emphasis is italic, no bold headings.
3. Logos are the supplied files, correct tone for the ground, clear space respected.
4. Every finding, baseline and risk shows its evidence status.
5. Every number that came from a source names the source in the row or a note.
6. No stock imagery. Supplied brand photography only where it carries information.
7. An overlong render is cut, never shrunk (rule 15).

## Variance hooks

- Cover: dark field with negative mark, or brand ground with positive mark and a single accent rule.
- Plan: three columns, or a transit-map drawing from `aesthetic-library.md` direction 16 using brand colors.
- Metrics: tiles, or a single variance table.
