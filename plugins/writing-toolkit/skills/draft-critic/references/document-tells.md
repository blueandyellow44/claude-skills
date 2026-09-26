# Generated-document tells

Load this when a program, template, or mail merge produced the document and a client or counterparty
will read it: a rendered report, a proposal built from form answers, an audit summary. These are the
tells a skeptical reader hits first, roughly in the order they hit them. Each was found in a real
shipped document.

1. **Totals that do not add up.** A headline number the document's own rows cannot reproduce ("8
   processes, 1,911 hours" over five listed items summing to 1,875). The first thing a finance reader
   does is add the visible rows. Every figure must be recomputable from what the page shows.
2. **False precision on estimates.** "Roughly 1,911 hours" is four significant figures wearing the word
   roughly. Sums of rough estimates get rounded to the precision of their inputs.
3. **Labels jammed into sentence frames.** "It starts when a date on the calendar" is a dropdown value
   pasted after a template stem. Read every slot-filled sentence aloud with each possible value.
4. **Verbatim self-repetition.** The same sentence rendered twice because two items had the same inputs.
   Search the document against itself for repeated sentences.
5. **Internal vocabulary leaking out.** "Each point of effort returns about 125 hours" means nothing to a
   reader who never saw the scoring model. Scores and weights stay internal; the text says what they
   mean in words.
6. **Unattributed "we".** A stakeholder's "we look disorganized" pasted into the consultant's document
   makes "we" the consultant. Quote interior voices or put them in the third person.
7. **Claims the document contradicts.** A headline adjective ("total addressable hours") that includes
   items a later caveat marks as blocked. Check every headline claim against the caveats.
8. **Inflated counts of people.** "Five stakeholder interviews" with four people ever named. Counts of
   human activity must match the named humans.
9. **The unexamined load-bearing number.** The whole recommendation rests on one implausible input
   (a report run 250 times a year) that nobody flagged. Name the biggest single input as an assumption
   and say how to verify it.
10. **A recommendation with nothing to sign.** No price, no timeline, no next step. A document meant to
    persuade ends with an explicit ask.

## Method

- Grade blind if you can: the document and this list, without the author's notes. Self-grades run soft.
- Fixes belong in the generator or template, not the one document, or the next document repeats them.
- Report these under a separate `Document tells` heading in the verdict, each with the quoted evidence.
