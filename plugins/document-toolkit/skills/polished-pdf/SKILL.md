---
name: polished-pdf
description: Build PDF documents that look designed, not generated. Use when the user needs an annual report, invitation, research report, formal letter, rebuttal, planning document, board report or other branded document and wants it to read as if a graphic designer made it, not a word processor. Triggers on "make a polished PDF", "design a PDF", "lay out a report", "create an invitation PDF", "render this as a designed document". Can also match a document to a specific organization's own brand from its brand guide, website, logo files or tokens ("match our brand", "make it look like their website", "use the brand guide in this folder"), and offers an 18-direction aesthetic library beyond the four core aesthetics (editorial, corporate, brand, warm). Renders HTML through Chromium.
---

# polished-pdf

You produce polished PDF documents by writing HTML and rendering it through headless Chromium (Playwright or `chrome --headless`). The single outcome is a PDF that does not look like an AI generated it. Every interactive prompt goes through `AskUserQuestion`, except in an unattended run (see **Unattended runs**).

All paths below are relative to this skill's folder (the base directory the Skill tool reports for this skill).

## Required reads on trigger

### MANDATORY, READ ENTIRE FILE before Step 1

1. `references/design-tokens-base.md` for the shared typographic scale, spacing rhythm and semantic tokens.
2. `references/interface-design-patterns.md` for the intent-first design discipline.
3. `references/soft-ui-patterns.md` for high-end craft patterns adapted to print.
4. `examples/` (all files) so the skill learns from approved outputs. If the folder contains only `README.md`, skip this read.

### Conditional loads (only after the matching step)

- `references/brand-matching.md` when Step 1 takes the **Match a brand** path. Run `scripts/extract_brand.py` as that file directs.
- `references/aesthetic-library.md` when Step 1 takes the **Pick a direction** path, or when brand evidence is too thin to match.
- `references/templates/matched-board-report.md` when a matched brand meets a board report, board pack, investment memo, operating review or turnaround plan.
- `references/design-tokens-<aesthetic>.md` after Step 1 locks the aesthetic. Load only the file matching the locked aesthetic.
- `references/templates/<aesthetic>-<doc-type>.md` after Step 2 locks the doc type.
- The owning organization's own brand guide, logo files or tokens, only once you have confirmed whose document this is. A locked `brand` aesthetic is not sufficient on its own: `brand` names a visual style, not an owner. For a client, a third party or an invented company, take colors, type and marks from that party's own brand evidence.

### Do NOT load

- The design-tokens files for aesthetics NOT chosen at Step 1. If aesthetic = editorial, do not load `design-tokens-corporate.md`, `design-tokens-brand.md` or `design-tokens-warm.md`.
- Any template file outside the locked aesthetic. If aesthetic = editorial, do not load templates under `corporate-*.md` or `brand-*.md`.

If any MANDATORY read is missing in an attended run, surface the gap and stop before continuing. If a conditional load fails, route to the build-template sub-interview in Step 2.

## Unattended runs

A run is unattended when no human will answer: a scheduled, scripted or headless run (`claude -p`), a request to finish autonomously, or `AskUserQuestion` unavailable or erroring. The steps below then change as stated; the templates, design tokens, render QA and every rule still apply.

- **Reads.** Files in this skill's own folder are mandatory. A missing optional input (a brand guide, a style note) goes in the build notes and the run continues.
- **Voice.** Follow the request's instructions in plain professional prose. If the user has a house style or voice guide in the working folder, use it. No em dashes in generated HTML unless the request asks for them; `render_pdf.py` checks.
- **Step 1.** Take the unattended rule already in Step 1: brand evidence for the document's owner in the working folder means Match; otherwise pick one library direction from the reader's world. Log the choice and its reason.
- **Step 2.** Use the closest built template (a board report, board pack, operating review or planning document uses `matched-board-report` when a brand profile exists, otherwise `editorial-research-report`). If none fits, build the smallest content-specific variant in the working directory. Never run the template sub-interview.
- **Step 3.** Answer the three intent questions yourself from the request and record them in the build notes. Content comes from the request and the supplied material; missing blocks become visible Known / Inferred / Needs data statements in the document, not questions.
- **Step 4.** Build in `./polished-pdf-build/<slug>/` under the current working directory. Derive the slug from the title. **Write the HTML in parts, never in one response:** a single response has an output token cap, and a long document written in one `Write` can exceed it and end the run with no PDF. Write the head, styles and cover first, then append one section per `Edit`, keeping every call under about 6,000 words of output.
- **Step 5.** No browser preview loop. Render with `scripts/render_pdf.py`, read every page thumbnail it writes, fix what they show, and re-render at least once before accepting.
- **Step 6.** Save the PDF in the working directory, or at the path the request names. Do not ask.
- **Step 7.** Skip the open and save-as-example questions.

## Step 0: prerequisite check (refusal gate 1)

Before Step 1, verify these reference files exist:

- `references/design-tokens-base.md` and the four aesthetic token files.
- `references/interface-design-patterns.md` and `references/soft-ui-patterns.md`.

If any are missing AND the user declines to build them now, refuse to proceed. Save the partial work to the build folder and exit clean. Tell the user which references are missing.

If the chosen template scaffold (Step 2) does not exist yet, it counts as a missing reference and triggers the same refusal gate.

## Step 1: pick the path, then the look

### 1a. Choose the path

First decide which of three paths this document takes. Look in the working folder and the request before asking.

- **Match a brand.** The document belongs to a specific organization and evidence of its brand exists: a brand guide, logo files, tokens or CSS, a website URL, or earlier company documents. Load `references/brand-matching.md`, run the extractor, build and confirm the brand profile, then go to Step 2.
- **Pick a direction.** No owning brand, or the user wants something new. Load `references/aesthetic-library.md` and offer three directions that differ in kind (one restrained, one structural, one expressive), each rooted in the reader's world. Show a small text preview of each through `AskUserQuestion`.
- **Use a core aesthetic.** The user names editorial, corporate, brand or warm, or reuses an approved example. Continue with 1b.

Rules for this step:

- **A free-text answer that does not name an option is not a lock.** "Something bold", "surprise me" or "show me what you can do" means offer new options from the library, never default to a previously approved variant.
- **Subject matter does not choose the aesthetic.** A document about an organization is not automatically in that organization's brand; ownership and the user's choice decide.
- **When no human will answer** (a scheduled, scripted or unattended run where questions get "proceed using your best judgment"): if the working folder holds brand materials for the organization the document is written for, take the Match path and confirm roles from the evidence yourself. Otherwise pick one library direction from the reader's world. Write the choice and its reason into the build notes, and do not stall on a question.

### 1b. Core aesthetics

Ask via `AskUserQuestion` with four options:

- **Editorial** (Stripe Press style): serif body, generous white space, restrained color, book-like.
- **Corporate** (Edelman / McKinsey style): bold cover, full-bleed photography, color blocks, data spreads.
- **Brand** (Mailchimp / Notion style): friendly illustration, brand color everywhere, playful but precise type. When the document belongs to an organization with a real identity, use that organization's real values (from its guide, or via the Match path), not the generic fallbacks in `design-tokens-brand.md`. If a render under this aesthetic still looks generic, the cause is more likely a layout or richness gap (rule 13: use functional color across rails, table headers, data emphasis, callout bands) than missing brand inputs.
- **Warm**: full-bleed location photography, a warm cream page, a rotating rust, gold and brown accent set, colored stat tiles and table headers. The one aesthetic sanctioned to break the white-page rule. Best for planning documents, decision briefs and personal research, not formal correspondence or third-party brand work. Do not pick it for an organization's branded document unless the user explicitly asks for it on that document.

MANDATORY, READ ENTIRE FILE on the matching design tokens file (`references/design-tokens-<aesthetic>.md`). Do NOT load the other three. Lock the aesthetic for the rest of the run; no aesthetic switch later without restarting.

## Step 2: pick document type

Ask via `AskUserQuestion` with options drawn from the chosen aesthetic:

- **Editorial**: research report, long-form essay, white paper, book interior, formal letter, field guide.
- **Corporate**: annual report, investor deck, business review, market analysis.
- **Brand**: invitation, marketing PDF, internal team doc, internal report, lookbook, event recap.
- **Warm**: no doc types built yet. First real use runs the build-template sub-interview below.
- **Matched (any brand)**: `board-report`. Other doc types reuse the closest core template with the brand profile's tokens substituted, and the substitution is noted in the build notes.
- **Library directions**: no templates. Build from the direction's fields in `references/aesthetic-library.md`; the first approved render of a direction can be saved to `examples/`.
- **Screenplay**: `screenplay-scene`, a fixed industry format rather than a design choice.

MANDATORY, READ ENTIRE FILE on the matching template scaffold (`references/templates/<aesthetic>-<doc-type>.md`).

If the scaffold does not exist yet, surface the gap and ask the user via `AskUserQuestion`: build the template now via a sub-interview, fall back to the closest available template, or exit.

### Build-template sub-interview (when chosen template is missing)

If the user chooses "build the template now," run a focused four-question sub-interview via `AskUserQuestion`, one question at a time, each with a recommended answer.

1. **Content blocks.** What blocks does this doc type expect? Recommend a starter schema based on doc-type conventions (for example, for `editorial-formal-letter`: date, subject, filing note, body, signature, closing). Confirm or revise.
2. **Page geometry.** Page size and margins. Recommend Letter portrait with 0.85 in margins for letter doc types; Letter with 0.75 in for report doc types; A5 for invitations. Confirm or revise.
3. **Variance hooks.** Which one element of the layout can vary between runs of this template (hero treatment, section opener, blockquote style). Recommend the option closest to the existing aesthetic's variance pattern. Confirm or revise.
4. **Hard rules.** Anything this doc type should never do (for example, never justify, never break a quote across pages). Recommend the locked aesthetic's hard rules as the default. Confirm or revise.

Write the new template to `references/templates/<aesthetic>-<doc-type>.md` in this skill's folder (or to the working directory if the skill folder is read-only), with the same structure as the existing templates: content-block schema table, HTML scaffold, render notes, hard rules, variance hooks. Add it to the "Doc types built so far" list in `references/design-tokens-<aesthetic>.md`.

Then resume Step 2 with the new template loaded.

## Step 3: collect content (refusal gate 2)

### Before parsing, hold an internal answer to three intent questions

Adapted from `references/interface-design-patterns.md`. You must have a working answer to each before rendering. If unclear, ask the user via `AskUserQuestion` and lock the answers before continuing.

1. **Who is this for?** The actual person who reads the PDF. Not "users." Where are they when they open it? What is on their mind?
2. **What must they accomplish?** The verb. Decide, approve, file, RSVP, sign, attach. The answer determines what leads, what follows, what hides.
3. **What should this feel like?** Concrete words. Warm like a notebook. Cold like a quarterly filing. Quiet like a Sunday. Firm like a closing argument.

Two formal letters rendered for two different situations should reflect their specifics in typography weight, blockquote treatment and page rhythm. If you cannot tell the answers apart between this document and a hypothetical other document in the same template, the render will look generic.

### Collect content

Ask via `AskUserQuestion` how content arrives:

- Paste into chat.
- File path on disk.
- A note or document the user points to.

Read the content. Parse it into the doc type's content-block schema. Each doc type defines its own schema inside its template scaffold file.

If the content has zero recognizable blocks (truly empty, or unparseable into any expected block), refuse to proceed. Tell the user which blocks were expected and what the input looked like. Save the partial work and exit clean.

If some blocks are missing but others fit, surface the gaps via `AskUserQuestion`: fill the missing blocks now (the user types them in chat), use placeholder content, or restructure to a doc type the input actually fits.

## Step 4: fill template

Render the template scaffold with the parsed content. Apply the chosen design tokens. Save to a working HTML file at `./polished-pdf-build/<slug>/draft.html` under the current working directory. The slug is derived from the doc title; if the user has not given one, ask once via `AskUserQuestion`. Example: for "Quarterly Operations Review, Q3", the slug would be `quarterly-operations-review-q3`.

For long documents, write the HTML in parts as described under **Unattended runs**, Step 4.

## Step 5: preview and iterate

Show the HTML preview to the user in a browser (for example through a Chrome automation MCP, or by opening `file://<path-to-draft.html>`). Ask via `AskUserQuestion`:

- Approve and render.
- Adjust design tokens (color, type, spacing).
- Adjust content layout (move blocks, change section order).
- Restart with a different template.

Loop until the user approves.

## Step 6: render PDF

Render and QA in one step:

```sh
python3 scripts/render_pdf.py draft.html out.pdf --expect-fonts "<families>" --ground "<page ground>" [--skip-ground-pages 1]
```

It waits for web fonts, prints backgrounds, and exits non-zero when an expected font did not load, a page is off its ground color, or an em dash is present. Then read every page thumbnail it writes. Fall back to `chrome --headless --print-to-pdf` only if Playwright is unavailable.

Ask the user via `AskUserQuestion` where the rendered PDF should land (no default save location; ask every run). Suggest:

- `./polished-pdf-build/<slug>/<slug>-<YYYY-MM-DD>.pdf`
- `~/Documents/<slug>-<YYYY-MM-DD>.pdf`
- Custom path.

If rendering fails, capture the verbose error log, retry once, and if it fails again surface the full log to the user and exit clean. In a sandboxed environment, prefer Playwright's bundled Chromium (`python3 -m playwright install chromium`). On a desktop machine with Chrome installed, the system Chrome also works.

## Step 7: save and offer to keep as an example

Save the rendered PDF at the chosen path. Offer via `AskUserQuestion`:

- Open it now.
- Save a copy to a different path.
- End.

Then ask: save this output as a good example?

- Yes.
- Yes with notes.
- No.

If yes, write the input, the rendered HTML (or its path), the PDF path and any notes to `examples/YYYY-MM-DD-HHMM.md` in this skill's folder. See `examples/README.md`.

## Connectors and tools

- `Bash`: rendering through `scripts/render_pdf.py` or `chrome --headless`
- `Read`, `Write`, `Edit`: HTML scaffolding
- `AskUserQuestion`: every interactive prompt
- An image-generation tool, if available: inline imagery when a template calls for it
- A browser automation tool, if available: live HTML preview before render

## Rules

1. **Reading the reference files is obligatory.** Each step that names a reference must read it. Do not skip.
2. **Human in the loop returns variations.** When asking the user for a design choice, return three or four options through `AskUserQuestion`. Single answers are an anti-pattern.
3. **Plain prose.** Plain words and no em dashes in generated prose unless the user asks otherwise. If the user supplies a voice or style guide, follow it for any content written under their name.
4. **No silent template substitution.** If the chosen template's expected content blocks do not match the input content, surface the mismatch and ask the user what to do. Do not silently drop or fill in content.
5. **PDF render failures retry once with verbose logging.** If rendering fails, capture the error, retry once, and if it fails again surface the error with the verbose log instead of returning a blank PDF.
6. **Content overflow or underfill is a surfaced question, not a silent decision.** When content does not fit the template's expected size, ask whether to truncate, paginate or restructure. Do not auto-truncate.
7. **Image generation failure falls back to a placeholder.** If the image tool is unreachable or rate-limited, drop a clearly marked placeholder block and continue. Do not block the whole run on one missing image.
8. **Missing tooling exits clean with the install one-liner.** If no Chromium is installed or it fails to boot after retry, surface the install command and exit. Do not return a blank PDF.
9. **Self update.** When the user says something should not happen again, add it to this rules section. When the user approves an output, offer to save it under `examples/`.
10. **Refuse on both gates.** Step 0 prerequisite check and Step 3 unparseable content. Either firing means a guaranteed bad output, so the skill exits clean instead of shipping junk.
11. **Page background is always white for any document intended for print, for every aesthetic except `warm` and a matched brand's own ground.** No cream, no amber, no two-tone, no `@media` split. `warm` is the sanctioned exception: its cream page is fixed across every render mode, the same consistency principle applied to a different color. Any accent color in `warm` must carry `print-color-adjust: exact` or it can silently drop in Chrome's headless print path; see `references/design-tokens-warm.md`.
12. **Never ask the user to do something the skill can do.** If a file write, copy, render or shell command is within reach of your tools, do it directly. Handing the user a one-liner is the last resort, not the first.
13. **Print-safe is a floor, not an aesthetic.** Keep the page white and preserve grayscale legibility, but when the user asks for a visually impressive or digital-first PDF, use functional color across section rails, table headers, data emphasis and callout bands. Color may reinforce hierarchy but may never be the only carrier of meaning.
14. **The template must fit the work.** A campaign playbook should read like a campaign briefing book. A technical audit should read like a technical audit. Do not force specialized material into the nearest generic report scaffold. Build one visual grammar from the content's real operating context, then repeat it consistently.
15. **An overlong render is fixed by cutting content, never by tightening CSS.** If the user flags a rendered document as too long, check first for forced page breaks (`page-break-before: always` on every section regardless of length) and for duplicated content (the same facts or list stated more than once), and remove those. Only touch spacing tokens after real redundancy is gone. Shrinking padding to hit a page count is a trick, not a fix.
16. **A brand match invents nothing.** Every color, face, mark and rule comes from the brand's own evidence, with its source recorded. A missing value is marked unknown or a named substitute, never guessed silently. The brand's own specified fonts override the banned-font list.
17. **Any non-white page ground is set on `@page` as well as `body`.** Chrome paints body backgrounds only inside the page margins, so without `@page { background: ... }` interior pages print with a white frame. Applies to matched brand grounds and to `warm`.
18. **Never present a PDF label as a working button.** PDF clipboard actions are viewer-dependent and cannot be promised. A print artifact says "Select text to copy"; actual Copy buttons live in HTML opened in a browser. Test every such button by reading the clipboard back and comparing it byte for byte with the source text. A button changing to "Copied" is not evidence that anything reached the clipboard.

## Anti-patterns

Do not:

- Put one organization's brand on another organization's document. Resolve whose document this is before a mark, wordmark, color system, byline or company name goes anywhere near it. Brand assets sitting in a folder prove a brand exists, never whose document this is or that you may use it.
- Inherit identity from a prior run's artifact. A past render is a record, not a reusable scaffold. Reusable templates live only under `references/templates/`.
- Pick a template aesthetic without asking in an attended run. An unattended run follows **Unattended runs**.
- Try to support several aesthetics in a single template. They are locked at Step 1 by design.
- Skip the reference reads. Each design tokens file and each template scaffold must be loaded before rendering.
- Use em dashes in the HTML the skill generates, unless the user asks for them.
- Use any of the banned fonts from `references/soft-ui-patterns.md` (Inter, Roboto, Arial, Open Sans, Helvetica) without an explicit override from the user or a brand that specifies them.
- Render to PDF before the user has previewed the HTML in Step 5 of an attended run. An unattended run reviews the render thumbnails instead.
- Apply a tinted page background and then split it across `@media print` vs `@media screen`. The page tone cannot vary by render mode, in any aesthetic including `warm`.
- Justify body text in editorial doc types. Justification creates rivers in 11 pt serif prose. Left-aligned with a ragged right edge, every time.
- Use the `--accent` color anywhere except a thin rule (blockquote left border, hairline) without explicit user consent, in editorial, corporate or brand. A colored heading, a colored paragraph or a colored background fill all violate the print-friendly rule for those three aesthetics. `warm` is the named exception (stat tiles, table headers, the cover band, a rotating card-border accent) and carries its own hard rules in `references/design-tokens-warm.md`.
- Treat a request for more color as permission to decorate every block. Use color by function, and make sure the hierarchy still works in grayscale; keep the page white in editorial, corporate and brand, cream in `warm`.
- Reach for rounded evidence cards, gradients, floating badges, icon grids or a generic dashboard layout because they look polished in isolation. Those motifs are common AI tells when they do not arise from the document's actual work.
- Reuse an existing template merely because it exists when its visual grammar does not fit the content. State the mismatch and build the smallest content-specific variant instead.
- Load design-tokens or template files for an aesthetic that was not locked in Step 1. It wastes context and dilutes the active design system.
- Hand the user a one-liner when the skill could have done the operation directly. Do the work, then say what was done.

## Known scope limits

Templates fully built so far: `editorial-research-report.md`, `editorial-formal-letter.md`, `editorial-field-guide.md`, `brand-internal-report.md`, `brand-lookbook.md`, `matched-board-report.md`, `screenplay-scene.md`. Scripts: `scripts/extract_brand.py` (brand evidence from folders, PDFs, SVGs, CSS or URLs) and `scripts/render_pdf.py` (render plus QA). The aesthetic library carries 18 directions without templates. Every other doc-type combination, including every doc type under `warm`, is deferred. The first run that picks one of them surfaces the missing-template gap and runs the build-template sub-interview in Step 2.

This is intentional: build the small version first, learn from real use, expand. Each template added later goes into `references/templates/<aesthetic>-<doc-type>.md` and is immediately usable.

## Files in this skill

- `references/design-tokens-base.md`, `design-tokens-editorial.md`, `design-tokens-corporate.md`, `design-tokens-brand.md`, `design-tokens-warm.md`
- `references/interface-design-patterns.md`, `references/soft-ui-patterns.md`
- `references/aesthetic-library.md`, `references/brand-matching.md`
- `references/templates/` (one file per built doc type)
- `scripts/render_pdf.py`, `scripts/extract_brand.py`
- `examples/README.md` (approved renders are saved alongside it)

## Dependencies

- Python 3.
- `playwright` with Chromium for rendering (`pip install playwright` then `python3 -m playwright install chromium`), or a system Chrome.
- `pymupdf` for render QA and PDF brand extraction (`pip install pymupdf`).
- `pillow` (optional) for raster color clustering in `extract_brand.py`.
