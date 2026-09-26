Patterns adapted from the `design:interface-design` plugin SKILL.md. The original is for screen interfaces (dashboards and apps); this extract distills the intent-first design discipline and adapts it for print PDF documents. Read on every polished-pdf run.

## Where defaults hide

In print as in screen, defaults disguise themselves as infrastructure.

- **Typography feels like a container.** It is not. Typography is the design. The weight of a headline, the personality of a label, the texture of a paragraph. An annual report for a sustainability nonprofit and a research report for a quant hedge fund both need "clean readable type" but the type that is warm and editorial is not the type that is cold and data-precise. If polished-pdf is reaching for the same font stack on both, the design is wrong.
- **Layout feels like scaffolding.** It is not. Layout is the document. Where the eye lands first, where it rests, what gets emphasized by isolation. A page floating in space is a template demo, not a document.
- **Data feels like presentation.** It is not. A number on a page is not design. The question is what does this number mean to the person looking at it. A KPI in a 72 pt accent color tells one story; the same KPI in body type tells another. If polished-pdf is rendering a number-on-a-label and walking away, it is not designing.
- **Token names feel like implementation detail.** They are not. `--ink` and `--paper` evoke a world. `--text-primary` and `--bg-secondary` evoke a template. The token names in the design-tokens files were chosen deliberately.

## Intent first

Before rendering any HTML, polished-pdf should have an internal answer to:

- **Who is this for?** Not "users." The actual person reading this document. Where are they when they open it? What is on their mind?
- **What must they accomplish?** Not "read the report." The verb. Decide whether to invest. Approve the budget. RSVP to the event. The answer determines what leads, what follows, what hides.
- **What should this feel like?** Say it in concrete words. Warm like a notebook. Cold like a quarterly filing. Quiet like a Sunday. The answer shapes everything downstream.

If polished-pdf cannot answer these for the document being rendered, surface the gap to the user via `AskUserQuestion` in Step 3 (collect content) or Step 5 (preview and iterate). Do not guess.

## Every choice must be a choice

For every design decision polished-pdf makes during a render:

- Why this aesthetic and not another?
- Why this color emphasis?
- Why this spacing scale?
- Why this information hierarchy?

If the answer is "it is common" or "it is clean" or "it works," that is a default, not a choice. The interface-design source skill calls this the sameness failure: "If another AI, given a similar prompt, would produce substantially the same output, you have failed."

In polished-pdf this means: two annual reports rendered by this skill for two different organizations should not look like the same template with different logos. Two formal rebuttal letters rendered for two different people should reflect the specifics of each situation in typography weight, blockquote treatment, and page rhythm.

## Intent must be systemic

Stating an intent and then defaulting anyway is the most common failure mode. If the chosen intent is "warm," every token (surfaces, text, borders, accents, semantic colors, typography) must reinforce that. Check your output against your stated intent.

## What polished-pdf takes from this

- Intent comes before tokens. If the intent is unclear, ask the user via `AskUserQuestion` before rendering.
- Every render is a chance to choose, not default. If polished-pdf rendered something that looks like every other PDF in the same template, that is failure.
- Token names are design decisions. Use the semantic names defined in the design-tokens files; never bypass them with raw hex values in templates.
- AI tells in color choices: "muted navy" is a common one. Pick palettes that feel intentional and earned rather than reaching for the default professional color palette.

## Related

- `design-tokens-base.md`
- `soft-ui-patterns.md`
- Source plugin: `design:interface-design`
