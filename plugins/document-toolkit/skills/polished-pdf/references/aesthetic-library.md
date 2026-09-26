# Aesthetic library

Read this file when Step 1 takes the **Pick a direction** path, or when the **Match a brand** path finds too little brand evidence and needs a direction that sits naturally beside what exists.

The four original aesthetics keep their own token files and templates: `editorial`, `corporate`, `brand` (the route for a document owned by an organization with its own identity), and `warm`. The directions below are new. Each is a starting system, not a finished template: pick one, then derive tokens from the document's real subject.

## How to choose

1. **Start from the reader's world, not from taste.** Where will this be read, by whom, and what do documents in that world already look like? A lab notebook for research, an edit bay for video, a filing for finance.
2. **Offer three that differ in kind.** When asking the user, never offer three variations of the same look. Mix one restrained, one structural and one expressive direction.
3. **Check the AI-tell list before offering.** If a direction lands on one of the looks below without a reason rooted in the subject, do not offer it.
4. **Record the choice.** Name the direction in the build notes and the examples log so the next run can avoid repeating it (variance mandate).

## The AI-tell looks to avoid by default

These cluster in generated documents. Use one only when the user names it or the brand already is it.

- Warm cream page, serif display, terracotta or rust accent.
- Near-black ground with one acid green, vermilion or electric pop.
- Broadsheet hairlines with dense newspaper columns.
- Purple to blue gradient hero on white.
- Inter or Space Grotesk as the neutral default face.
- Rounded cards with a colored left rail on every block.
- Emoji or icon grids as section markers.
- Everything centered.
- Numbered section markers (01, 02, 03) on content that is not a sequence.
- Muted navy plus gold "consulting" palette.

## Directions

Font stacks name a Google Fonts family first, then Mac-installed fallbacks. Confirm loading before render.

### 1. Swiss grid
- **Feels like:** a 1960s transit manual. Certain, unadorned.
- **Fits:** strategy decisions, operating plans, anything where structure is the argument.
- **Type:** Archivo or "Neue Haas Grotesk" if licensed; fallback "Helvetica Neue". One family, three weights. Numerals huge.
- **Palette:** white, true black, one signal color used as solid blocks (signal red `#E3120B`, or a subject-derived hue), one light gray.
- **Layout:** strict 12-column asymmetric grid, flush-left ragged, huge numbers bleeding to the margin, generous empty columns.
- **Signature:** a full-bleed statistic page.
- **Traps:** do not soften corners or add cards; do not center anything.

### 2. Edit bay
- **Feels like:** a video editing timeline.
- **Fits:** anything about video, time, sequence, retention, production.
- **Type:** "IBM Plex Sans Condensed" for heads, "IBM Plex Mono" for timecodes and data.
- **Palette:** graphite `#1E2124` bands, off-white page `#F4F5F2`, broadcast color bars as markers (`#FFC20E`, `#00A3E0`, `#E4002B`, `#00A651`), each assigned to one track.
- **Layout:** a horizontal timeline ribbon that sections hang from; timecode labels (`00:01:40:00`) as section eyebrows; tracks as rows.
- **Signature:** data drawn as a waveform or clip strip.
- **Traps:** do not go full dark page; do not use neon glow.

### 3. Lab notebook
- **Feels like:** a researcher's bound notebook.
- **Fits:** experiments, audits, investigations, anything with hypotheses and results.
- **Type:** "Source Serif 4" body, "JetBrains Mono" data, "Caveat" only for margin annotations, sparingly.
- **Palette:** white page with faint blue 5 mm grid `#DCE6F2`, blueprint ink `#1F3A68`, red pen `#C62828` for corrections only.
- **Layout:** dated entries, numbered figures, evidence taped in as slips with a paper-edge shadowless border, hand annotations circling the key number.
- **Signature:** the chart looks plotted by hand on the grid, with one red-pen note.
- **Traps:** handwriting stays under five annotations per page; never body text.

### 4. Annual filing
- **Feels like:** an SEC filing crossed with a well-set ledger.
- **Fits:** finance, board packs, turnarounds, liquidity, anything a CFO checks.
- **Type:** "Libre Franklin" heads, "Newsreader" or "Charter" body, tabular lining numerals everywhere.
- **Palette:** white, ink `#111`, one institutional green `#1B5E3B` or the company's color, red for negative numbers only.
- **Layout:** numbered notes, dense but aligned tables, decimal-aligned columns, footnote references, a restrained cover with a single rule.
- **Signature:** a variance table where negatives are parenthesized and red.
- **Traps:** do not add icons or stock photography.

### 5. Blueprint
- **Feels like:** an architectural drawing set.
- **Fits:** systems, architecture, process maps, technical plans.
- **Type:** "Barlow Semi Condensed" heads, "IBM Plex Mono" callouts.
- **Palette:** white page, cyanotype blue `#0B3D91` line work, one amber `#F2A900` for revisions.
- **Layout:** title block in the lower right of every page (sheet number, revision, date), dimension-line callouts, section cuts.
- **Signature:** the sheet title block.
- **Traps:** avoid full blue backgrounds; blueprint lives in the linework.

### 6. Quiet hospitality
- **Feels like:** a small hotel's printed room book.
- **Fits:** hospitality, restaurants, retreats, experience brands without a guide.
- **Type:** "Cormorant Garamond" display at light weights, "Karla" body, small tracked capitals for labels.
- **Palette:** a stone or linen ground drawn from the subject's materials, one deep natural accent, lots of space.
- **Layout:** wide margins, few elements per page, captions set like menu items.
- **Signature:** one number or phrase per spread, set large and light.
- **Traps:** this sits next to the cream-serif AI look; justify it from real materials or skip it.

### 7. Museum catalogue
- **Feels like:** an exhibition catalogue.
- **Fits:** portfolios, case studies, collections, lookbooks.
- **Type:** "Fraunces" at low optical softness for display, "Work Sans" body.
- **Palette:** gallery white, warm gray wall `#E8E6E1` behind plates, black text.
- **Layout:** plate numbers, object labels (title, date, medium, dimensions), images centered on generous gray fields.
- **Signature:** the object label.
- **Traps:** do not caption like marketing copy.

### 8. Field guide
- **Feels like:** an Audubon or trail guide.
- **Fits:** trips, markets, ecosystems, category landscapes, competitor maps.
- **Type:** "Crimson Pro" body, "Oswald" labels.
- **Palette:** off-white, forest `#2F4F3A`, ochre `#C8912E`, sky `#7FA7B8`.
- **Layout:** species-card entries (identifying marks, habitat, range), range maps, quick-ID sidebars. Pairs with the existing `editorial-field-guide` template for trips.
- **Signature:** the identification card.
- **Traps:** keep it scannable; no long prose blocks.

### 9. Spec sheet
- **Feels like:** an industrial product data sheet.
- **Fits:** product specs, vendor comparisons, tooling, pricing sheets.
- **Type:** "Barlow Condensed" heads, "Barlow" body.
- **Palette:** white, black, safety yellow `#FFD100` or hazard orange `#FF6A13` as table header and warning bands only.
- **Layout:** spec tables with units in their own column, warning boxes, part numbers, a revision line in the footer.
- **Signature:** a hazard-striped callout for the one thing that must not be missed.
- **Traps:** hazard stripes once per document at most.

### 10. Modernist government report
- **Feels like:** a 1970s public-agency report.
- **Fits:** policy, public data, education, civic plans.
- **Type:** "Public Sans" heads and body, "IBM Plex Mono" data.
- **Palette:** white, agency blue `#005EA2` or green `#00843D`, one warm contrast `#E5A000`, gray tables.
- **Layout:** numbered paragraphs, figure and table numbering, big simple bar charts, a seal-like mark only if one exists.
- **Signature:** the numbered-paragraph finding.
- **Traps:** avoid clip-art icons.

### 11. Risograph zine
- **Feels like:** a two-color community print.
- **Fits:** community updates, workshops, creative briefs, informal internal culture pieces.
- **Type:** "Rubik" or "Bricolage Grotesque" heads, "Courier Prime" for typewriter notes.
- **Palette:** exactly two spot inks, for example fluorescent pink `#FF48B0` and teal `#00838A`, overprinting to a third.
- **Layout:** off-grid collage, halftone images, slight misregistration on purpose.
- **Signature:** overprint where the two inks cross.
- **Traps:** never for finance, legal or formal decisions.

### 12. Almanac
- **Feels like:** a farmer's almanac or sports record book.
- **Fits:** reference tables, calendars, historical data, stats-heavy reports.
- **Type:** "Old Standard TT" heads, "Libre Caslon Text" body, small caps.
- **Palette:** white, black, one oxide red `#9B2915` for rules and ornaments.
- **Layout:** dense ruled tables, running heads, small ornamental dividers, index at the back.
- **Signature:** a full-page table that reads cleanly.
- **Traps:** ornaments serve navigation only.

### 13. Product documentation
- **Feels like:** excellent developer docs.
- **Fits:** technical guides, API or workflow walkthroughs, internal playbooks.
- **Type:** "IBM Plex Sans" body, "IBM Plex Mono" code, headings in the same family.
- **Palette:** white, ink `#1B1F24`, one product color, code blocks on `#F6F8FA`.
- **Layout:** a left margin with section anchors, callouts typed as Note, Warning, Tip, code with line numbers, step lists that really are sequences.
- **Signature:** the annotated code or command block.
- **Traps:** avoid dark-mode code screenshots; set code as real text.

### 14. Magazine feature
- **Feels like:** a long-read feature spread.
- **Fits:** narrative case studies, profiles, essays with visuals.
- **Type:** "Playfair Display" is overused; use "DM Serif Display" or "Young Serif" display, "Literata" body.
- **Palette:** white, black, one editorial color taken from the lead image.
- **Layout:** a two-page opener, drop cap, pull quotes that break the column, image captions with credits.
- **Signature:** the opening spread.
- **Traps:** do not use broadsheet hairline columns.

### 15. Letterpress stationery
- **Feels like:** heavy cotton paper and one ink.
- **Fits:** letters, invitations, certificates, thank-you notes, formal announcements.
- **Type:** "EB Garamond" body, "Cinzel" only for a name or monogram.
- **Palette:** white, one ink color (oxblood `#5C1A1B`, deep green `#1F3D2B` or navy only if justified).
- **Layout:** centered only here, where the form is traditionally centered; generous margins; no rules except one under the letterhead.
- **Signature:** a monogram or single ornament.
- **Traps:** one ink means one ink.

### 16. Transit map
- **Feels like:** a subway diagram.
- **Fits:** roadmaps, multi-team plans, 30/60/90 day plans, dependency maps.
- **Type:** "Overpass" heads and labels, "Overpass Mono" dates.
- **Palette:** white, one color per workstream line (limit five), black station labels.
- **Layout:** workstreams drawn as lines at 45 and 90 degree angles, milestones as stations, interchanges where streams depend on each other.
- **Signature:** the plan drawn as the map.
- **Traps:** no more than five lines; label every station.

### 17. Newsroom data desk
- **Feels like:** a data journalism graphic page.
- **Fits:** analytics readouts, survey results, market sizing.
- **Type:** "Source Sans 3" labels, "Source Serif 4" headlines, tabular figures.
- **Palette:** white, ink, one highlight color for the story series, everything else gray.
- **Layout:** one chart per claim, a headline that states the finding, annotation text on the chart itself.
- **Signature:** the gray-everything-except-the-story chart.
- **Traps:** avoid dashboard tile grids.

### 18. Sports scouting report
- **Feels like:** a pro scouting file.
- **Fits:** competitive analysis, candidate evaluations, vendor bake-offs, team reviews.
- **Type:** "Saira Condensed" heads, "Saira" body.
- **Palette:** white, a team-style primary and secondary derived from the subject, gray bars.
- **Layout:** player-card profiles with graded attributes, strengths and weaknesses columns, comparison bars.
- **Signature:** the graded attribute card.
- **Traps:** grades must carry their reasoning in text beside them.

## Adding a direction

When a run builds a direction that is not here, add it to this file with the same fields. When a direction ships an approved render, save it under `examples/` so the variance check can see it.
