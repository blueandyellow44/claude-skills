Third fully-built template in polished-pdf, and the first built for a document that is carried rather than read. Stripe Press editorial aesthetic applied to a personal field guide: a day-by-day guide to a conference, trip, or run of events, with the logistics and the things to say in one artifact. Read this file when Step 2 locks aesthetic = editorial and doc-type = field-guide.

The other shipped types all assume a document read at a desk. This one assumes a phone screen or a folded page on a sidewalk.

## Intent this template encodes

The reader is standing up, outdoors, slightly late, and about to walk into a room where nobody knows them. They are not reading. They are checking one fact and then putting the page away. Every decision below follows from that.

- Scan time per page is three seconds, not three minutes. One day per page, never two.
- The left time rail is the navigation. The eye lands on a time before it lands on a name.
- Talking points are lines, never paragraphs. A paragraph cannot be read while walking.
- URLs are set at body size, not caption size, because they get typed into a phone by someone else.
- Status is stated plainly on every entry. A guide that implies a confirmed seat that is actually pending is worse than no guide.

## Content-block schema (refusal gate input)

| Block | Required | Description |
|---|---|---|
| `title` | yes | Name of the guide. String. |
| `subtitle` | no | One line. String. |
| `owner` | yes | Whose guide this is, and under what identity. String. |
| `span` | yes | Date range covered. String. |
| `basecamp` | no | Lodging and the transit facts that follow from it. `{name, detail, access, distances[]}`. |
| `identities` | no | When more than one name or title is in play. Array of `{context, name, org, title, email}`. |
| `days` | yes | 1 to 8 days. Each has `label`, `date`, `note`, `entries[]`, and optional `points[]` and `logistics`. |
| `days[].entries[]` | yes | `{time, name, host, loc, status, identity, kind}`. `kind` is one of `anchor`, `option`, `backup`, `travel`. |
| `demos` | no | What to show. Array of `{name, url, line, when}`. |
| `openers` | no | Talking points. Array of `{context, lines[]}`. |
| `cautions` | no | What not to promise. Array of strings. |

If `days` is empty or no day has entries, Step 3 refuses to proceed.

## Page geometry

US Letter portrait, 0.7 in margins. Tighter than the research report's 0.85 in because the page is scanned rather than read, and a wider text block costs a fold. Never A5: this prints on whatever is in the house.

## HTML scaffold

```html
<style>
  @page { size: 8.5in 11in; margin: 0.7in; }
  :root {
    --ink: #111111;
    --ink-muted: #4A4A4A;
    --ink-faint: #8A8A8A;
    --rule: #C9C9C9;
    --gold: #A87617;
  }
  html, body { background: #FFFFFF; }
  body {
    font-family: "Source Serif 4", Charter, "Hoefler Text", Georgia, serif;
    font-size: 11pt; line-height: 1.5; color: var(--ink);
  }
  .eyebrow {
    font-family: "Avenir Next", Optima, serif;
    font-size: 8pt; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ink-faint);
  }
  .day { page-break-after: always; page-break-inside: avoid; }
  .entry { display: grid; grid-template-columns: 0.85in 1fr; column-gap: 0.2in; }
  .entry .t {
    font-family: "Avenir Next", Optima, serif;
    font-size: 10pt; font-weight: 600; font-variant-numeric: tabular-nums;
  }
  .points { border-top: 1.5px solid var(--gold); padding-top: 0.1in; }
  .points li { margin-bottom: 0.06in; }
</style>
```

Full working scaffold lives in the run output; the block above is the load-bearing grammar.

## Render notes

- The time rail is a fixed-width grid column, not a float and not a table. Tabular numerals so 8:00a and 11:25a align on the colon.
- `kind` drives weight, never color alone. `anchor` is full ink, `option` is muted, `backup` is muted plus a hairline left rule, `travel` is faint italic. Grayscale must still carry the hierarchy.
- Gold is permitted on one thing per page: the hairline above a talking-points block. Nowhere else.
- Status words are set in the caption face and never abbreviated. "Pending host approval" beats "pending."

## Hard rules

1. **Page background is white.** Inherited, no exception.
2. **One day per page.** A day that splits across a page break defeats the artifact.
3. **Never state a location as confirmed when the host has not released it.** Write what is actually known, including "released on approval."
4. **No talking point longer than two lines.** If it needs three, it is a paragraph and it does not belong here.
5. **Left-aligned, no hyphenation, no justification.** Inherited.

## Variance hooks

- Cover: bottom-aligned block vs top-aligned with a rule.
- Day header: date set large with the weekday as eyebrow, vs weekday large with the date as caption.
- Talking-points block: gold hairline above vs gold left rule.

## What this template does not handle

- Anything with figures or charts. Use `editorial-research-report.md`.
- Anything read at a desk for longer than five minutes. Same.

## Related

- `design-tokens-base.md`
- `design-tokens-editorial.md`
- `editorial-research-report.md`
- `editorial-formal-letter.md`
