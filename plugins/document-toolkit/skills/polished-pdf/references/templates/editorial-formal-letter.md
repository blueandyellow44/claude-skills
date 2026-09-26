Editorial aesthetic adapted for the formal letter doc type. Reusable for any formal letter: rebuttals, complaints, escalations, formal responses.

**Lessons baked in.** The white-page-everywhere rule is not optional. Page tint cannot vary by render mode. The single allowed accent color is editorial gold (`#A87617`) on the blockquote left rule.

## Content-block schema

| Block | Required | Description |
|---|---|---|
| `title` | no | Optional letter title. Most formal letters do not have one. |
| `recipient` | no | "To: " block. Name, title, organization. Top of letterhead if present. |
| `sender` | no | "From: " block. |
| `date` | yes | Written date (e.g., "April 22, 2026"). Plain left-aligned text, not tiny caps. |
| `subject` | no | Subject line, prefixed automatically with "Re: ". |
| `filing_note` | no | One-paragraph instruction (e.g., "Please attach this rebuttal to..."). Renders before the body as plain italic gray, no border, no background. |
| `body` | yes | Main content as markdown. Markdown blockquotes (`> ...`) render as quoted notes with a thin gold left rule and italic gray text. Used heavily in rebuttals. |
| `signature` | no | Name plus optional role. Plain weight (not bold). |
| `closing_statement` | no | A distinct closing paragraph (e.g., rights preservation). Renders as a normal body paragraph, no italic, no top rule. |

## Refusal gate input

If `body` is empty or has no recognizable paragraphs, Step 3 refuses to proceed.

## HTML scaffold (v6, ships as v0.1)

Single column, white page edge to edge, gold accent only on blockquote left rules. Print-friendly: no background fills anywhere on the page.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ subject }}</title>
<style>
  @page { size: 8.5in 11in; margin: 0.85in; }
  :root {
    --ink: #111111;
    --ink-muted: #4A4A4A;
    --ink-faint: #888888;
    --rule: #C9C9C9;
    --gold: #A87617;
  }
  html, body { background: #FFFFFF; margin: 0; padding: 0; }
  body {
    font-family: "Source Serif 4", "Source Serif 4 Text", Georgia, serif;
    font-size: 11pt;
    line-height: 1.55;
    color: var(--ink);
  }
  .letterhead {
    border-bottom: 1px solid var(--rule);
    padding-bottom: 0.25in;
    margin-bottom: 0.3in;
  }
  .date {
    font-family: "Source Serif 4 Caption", serif;
    font-size: 10pt;
    color: var(--ink);
    margin-bottom: 0.1in;
  }
  .subject {
    font-family: "Source Serif 4 Subhead", serif;
    font-size: 11pt;
    color: var(--ink);
    font-weight: 600;
    margin: 0;
  }
  .filing-note {
    font-size: 10pt;
    color: var(--ink-muted);
    font-style: italic;
    margin-bottom: 0.3in;
  }
  .body p {
    margin: 0 0 0.16in;
    text-align: left;
    hyphens: none;
  }
  .body blockquote {
    margin: 0.18in 0 0.08in 0.25in;
    padding: 0 0 0 0.2in;
    border-left: 2px solid var(--gold);
    color: var(--ink-muted);
    font-size: 10pt;
    font-style: italic;
    font-family: "Source Serif 4", serif;
    page-break-inside: avoid;
  }
  .body ul { margin: 0 0 0.16in 0.25in; padding-left: 0; }
  .body ul li { margin-bottom: 0.04in; }
  .signature {
    margin-top: 0.4in;
    font-size: 11pt;
  }
  .signature .name {
    font-family: "Source Serif 4", serif;
    font-weight: 400;
  }
  .closing-statement {
    margin-top: 0.3in;
    font-size: 11pt;
    color: var(--ink);
  }
</style>
</head>
<body>
<div class="letterhead">
  <div class="date">{{ date }}</div>
  <div class="subject">Re: {{ subject }}</div>
</div>
{% if filing_note %}<div class="filing-note">{{ filing_note }}</div>{% endif %}
<div class="body">{{ body | safe }}</div>
{% if signature %}<div class="signature"><div class="name">{{ signature.name }}</div></div>{% endif %}
{% if closing_statement %}<div class="closing-statement">{{ closing_statement }}</div>{% endif %}
</body>
</html>
```

## Render notes

- Uses jinja2 substitution.
- Body markdown is pre-rendered to HTML before substitution. Blockquotes get the gold left rule; bulleted lists stay plain.
- Letterhead always renders the date and the "Re: ..." subject. Recipient and sender blocks are optional and not yet wired in this scaffold; add them when a future letter needs them.
- Filing note is plain italic, no border or background. Distinct from body by italic and gray color alone.
- Closing statement is a normal paragraph at body weight and color. No top rule, no italic.

## Hard rules (do not violate)

1. **Page background is always white.** No cream, no amber, no two-tone. The page is the same color in every render mode.
2. **The only color is the gold left rule on blockquotes.** No color elsewhere without explicit user consent.
3. **No justification, no hyphenation.**
4. **Source Serif 4 over Source Serif Pro.**

## Variance hooks

- Letterhead style: hairline rule below date+subject (default) vs no rule (more minimal).
- Blockquote style: gold left rule + italic gray (default) vs plain italic indent with no rule.
- Closing statement: plain paragraph (default) vs slightly smaller font for legal-style fine-print feel.

## What this template does not handle

- Tables or multi-column layouts.
- Photography or full-bleed imagery.
- Multi-page legal exhibits as inline content; use `filing_note` to direct the reader to attached exhibits.

## Related

- `design-tokens-base.md`
- `design-tokens-editorial.md`
- `interface-design-patterns.md`
- `soft-ui-patterns.md`
- `editorial-research-report.md` (sibling, same hard rules)
