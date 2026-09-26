Reusable template for rendering a single screenplay scene (or short sequence) in true US industry format: Courier 12pt, standard sluglines, indented character cues, the rigid margins a working script uses. Reusable for any screenplay scene under any project. This is a fourth aesthetic ("screenplay") distinct from editorial/corporate/brand, because industry format is a fixed published standard, not a design choice. Read this file when Step 2 locks doc-type = screenplay-scene.

## Content-block schema (refusal gate input)

| Block | Required | Description |
|---|---|---|
| `project` | no | Project or show title for the page-one header. String. |
| `episode` | no | Episode or sequence label for the header. String. |
| `open_transition` | no | Opening transition. Defaults to `FADE IN:`. |
| `scene_heading` | yes | The slug line, e.g. `INT. THE GEM - AL'S OFFICE - NIGHT`. Uppercased on render. Use hyphens, never em dashes. |
| `elements` | yes | Ordered array of scene elements. Each is `{type, ...}`. See element shapes below. |
| `close_transition` | no | Closing transition, e.g. `FADE OUT.`. |

Element shapes inside `elements`:

- `{type: "action", text}`: scene direction, flush left, full width, sentence case.
- `{type: "character", name, extension?}`: character cue, uppercased, indented. `extension` is the bracketed note like `CONT'D`, `V.O.`, `O.S.` rendered as `(CONT'D)`.
- `{type: "parenthetical", text}`: wryly/business note under a cue, indented inside the dialogue column, lowercase, in parentheses.
- `{type: "dialogue", text}`: spoken lines, indented dialogue column.
- `{type: "transition", text}`: `CUT TO:` etc., flush right, uppercased.

Re-cue rule: when an `action` block interrupts a single character's continuous speech and the same character resumes, the next `character` block carries `extension: "CONT'D"`.

If `elements` is empty or `scene_heading` is missing, Step 3 refuses to proceed.

## HTML scaffold (white-page-locked, Courier industry metrics)

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ scene_heading }}</title>
<style>
  @page { size: 8.5in 11in; margin: 1in 1in 1in 1.5in; }
  html, body { background: #FFFFFF; margin: 0; padding: 0; color: #000000; }
  body {
    font-family: "Courier Prime", "Courier New", Courier, monospace;
    font-size: 12pt;
    line-height: 1;
  }
  /* one blank 12pt line == 12pt of vertical space between blocks */
  .header { text-align: center; margin-bottom: 24pt; }
  .header .project { text-transform: uppercase; letter-spacing: 0.08em; }
  .header .episode { font-size: 12pt; }
  .transition-in { margin: 0 0 12pt 0; }
  .transition-out { text-align: right; margin: 24pt 0 0 0; text-transform: uppercase; }
  .slug { text-transform: uppercase; margin: 0 0 12pt 0; } /* scene heading: flush left, caps */
  .action { margin: 0 0 12pt 0; max-width: 6in; }
  .character { text-transform: uppercase; margin: 0 0 0 2.2in; } /* cue ~3.7in from page edge */
  .parenthetical { margin: 0 0 0 1.6in; max-width: 2.5in; }
  .dialogue { margin: 0 0 12pt 1.0in; max-width: 3.5in; } /* dialogue column ~2.5in from edge */
  /* keep a cue with its dialogue across page breaks */
  .character { page-break-after: avoid; }
  .slug { page-break-after: avoid; }
</style>
</head>
<body>

{% if project or episode %}
<div class="header">
  {% if project %}<div class="project">{{ project }}</div>{% endif %}
  {% if episode %}<div class="episode">{{ episode }}</div>{% endif %}
</div>
{% endif %}

<div class="transition-in">{{ open_transition or "FADE IN:" }}</div>

<div class="slug">{{ scene_heading }}</div>

{% for el in elements %}
  {% if el.type == "action" %}<div class="action">{{ el.text }}</div>
  {% elif el.type == "character" %}<div class="character">{{ el.name }}{% if el.extension %} ({{ el.extension }}){% endif %}</div>
  {% elif el.type == "parenthetical" %}<div class="parenthetical">({{ el.text }})</div>
  {% elif el.type == "dialogue" %}<div class="dialogue">{{ el.text }}</div>
  {% elif el.type == "transition" %}<div class="transition-out">{{ el.text }}</div>
  {% endif %}
{% endfor %}

{% if close_transition %}<div class="transition-out">{{ close_transition }}</div>{% endif %}

</body>
</html>
```

## Render notes

- Courier Prime is the screenplay standard; falls back to Courier New / Courier / monospace if the web font is unavailable in the headless renderer. Do not substitute a proportional font.
- Margins are the industry standard: 1in top/bottom/right, 1.5in left (binding side). Do not "design" them wider or narrower.
- Single-spaced within a block; one blank 12pt line between blocks (handled by the 12pt margin-bottom).
- Page background white in every mode (base rule 11).
- Page numbers: Chromium headless cannot render CSS `@page` margin-box counters reliably. If page numbers are required, supply them through the renderer's header/footer template, not CSS. Omitting them is acceptable for a single-scene excerpt.

## Hard rules

1. **Courier only.** Never a proportional or serif font. The format is the point.
2. **Sluglines uppercase, hyphens not em dashes.** `INT./EXT. PLACE - TIME`.
3. **Character cue indented ~2.2in, dialogue column ~1.0in, parenthetical ~1.6in** from the left text margin. These metrics are the standard; do not retune for looks.
4. **Re-cue with (CONT'D)** when action splits one character's continuous speech.
5. **Page background white. No design tinting.** Same as every print template.
6. **Do not edit the scene content to fit the page.** Overflow or a short last page is fine; screenplays run as long as they run.

## What this template does not handle

- Full scripts / multi-scene episodes with title pages and revision marks (build `screenplay-full.md` when needed).
- Dual-dialogue (two characters speaking simultaneously) beyond a single `dual` element stub.
- Production draft colored-revision pages.

## Related

- `design-tokens-base.md` (page + white-background discipline only; type scale is overridden by the Courier standard)
- `editorial-formal-letter.md`, `editorial-research-report.md` (sibling templates)
