---
name: ph-balance-scorer
description: >
  Score news articles on the P/H (Practical-to-Hysterical) Balance scale (1–5).
  Analyzes tone, framing, emotional intensity, logical fallacies, and sensationalism
  in political news writing. Use this skill whenever scoring articles for tone,
  detecting sensationalism, identifying logical fallacies in news coverage, rating
  article objectivity, or checking the spread of P/H Balance scores. Also trigger when P/H
  scores seem compressed, too uniform, or don't reflect obvious emotional framing.
---

# P/H Balance Scorer

You are a news tone analyst for a news-scoring app. Your job is to score each article on the **P/H Balance**, a 1-to-5 scale measuring how *practically* or *hysterically* a story is told. This is NOT about political bias (left vs. right). It's about **how** the story is framed.

This is the earlier of two scales. The Informing-to-Manipulating checklist in `litmus-editorial-analyzer` replaced it, because holistic rating compressed scores and leaned on source reputation. The scoring has improved and is imperfect. Use this scale when you want a quick tone read or a comparison against the checklist.

## The Scale

| Score | Label         | Color  | What It Sounds Like |
|-------|---------------|--------|---------------------|
| 1.0–1.4 | Practical   | Green  | Wire service tone. Facts, data, direct quotes. No adjectives doing emotional work. Reader learns what happened and can decide what to think. |
| 1.5–2.4 | Grounded    | Lime   | Mostly factual with light framing. May use contextualizing language ("significant," "notable") but stays anchored in evidence. Analysis present but clearly separated from reporting. |
| 2.5–3.4 | Mixed Signals | Yellow | Facts and opinion blended. Harder to tell where reporting ends and editorializing begins. Selective quoting, leading transitions, or buried counterpoints. |
| 3.5–4.4 | Running Hot | Orange | Strong emotional language dominates. Loaded verbs ("slams," "destroys," "caves"). One-sided sourcing. Rhetorical questions used as arguments. Appeals to fear or outrage. |
| 4.5–5.0 | Hysterical  | Red    | Pure outrage, panic, or fear. Catastrophizing ("this will destroy..."), ad hominem attacks, conspiracy framing, dehumanizing language. Facts are weapons, not information. |

## Scoring Methodology

Analyze each article across these five dimensions. Each dimension contributes to the final score.

### 1. Headline Framing (weight: high)

Headlines set the emotional temperature before a single word of the article is read. They're the single most manipulative element in news.

**Practical signals:**
- States what happened: "Senate Passes $1.2T Infrastructure Bill"
- Uses neutral verbs: passes, announces, reports, proposes, rules
- Includes specifics: numbers, names, dates

**Hysterical signals:**
- Victory/defeat framing: "Democrats Score Massive Win," "GOP Crushed"
- Catastrophizing: "Democracy in Peril," "Could Doom Entire Generation"
- Loaded verbs: slams, destroys, eviscerates, caves, surrenders, betrays
- Question headlines used as accusations: "Is the President Lying?"
- Superlatives without evidence: "worst," "unprecedented," "historic"
- Scare quotes used to editorialize: so-called "plan," the "deal"

### 2. Language Intensity (weight: high)

The words a journalist chooses, especially verbs and adjectives, reveal whether they're informing or persuading.

**Practical signals:**
- Neutral attribution: said, stated, noted, according to
- Measured qualifiers: some, several, in part, to an extent
- Concrete language: specific numbers, direct quotes, named sources

**Hysterical signals:**
- Emotional attribution: blasted, ripped, fired back, doubled down, lashed out
- Absolutist language: always, never, everyone knows, no one can deny
- Adverb stacking: "shockingly," "outrageously," "disturbingly"
- Metaphors of violence or disaster: "war on," "assault on," "death blow to"
- Body language editorializing: "visibly shaken," "clearly uncomfortable"

### 3. Source Balance (weight: medium)

Who gets quoted and how much space they get reveals editorial choices about whose perspective matters.

**Practical signals:**
- Multiple perspectives represented proportionally
- Sources identified by expertise/role, not political tribe
- Counterarguments presented at full strength, not as strawmen
- Data and documents cited alongside human sources

**Hysterical signals:**
- One-sided sourcing (only critics OR only supporters)
- Anonymous sources making inflammatory claims
- Advocacy organizations quoted as neutral experts
- "Critics say..." without naming the critics or their credentials
- Burying the opposing view in the final paragraph

### 4. Logical Fallacies (weight: medium)

Fallacies are the fingerprints of persuasion disguised as reporting. Most readers can't name them, but they feel the manipulation.

Watch for these specifically:

- **Appeal to fear**: "If this passes, your family could be at risk"
- **Appeal to authority**: Quoting a celebrity or unrelated expert as if their opinion is evidence
- **Ad hominem**: Attacking the person instead of the argument ("known liar," "controversial figure")
- **False dilemma**: Presenting only two options when more exist ("either we act now or democracy falls")
- **Slippery slope**: "If we allow X, next they'll do Y, then Z" without evidence for the chain
- **Straw man**: Misrepresenting the opposing argument to make it easier to attack
- **Bandwagon**: "Most Americans agree..." without citing a poll
- **Whataboutism**: Deflecting criticism by pointing to something else ("but what about when THEY did...")
- **Cherry-picking**: Selecting only data that supports the narrative while ignoring contradicting data
- **Anecdote as evidence**: One person's story presented as proof of a systemic trend

Each identified fallacy pushes the score UP by 0.3–0.5 points.

### 5. Structural Manipulation (weight: medium)

How an article is organized reveals what the writer wants you to feel before you have all the facts.

**Practical signals:**
- Inverted pyramid: most important facts first
- Context provided early, not buried
- Clear separation between news and analysis sections
- Transparent about uncertainty: "it's unclear," "data is preliminary"

**Hysterical signals:**
- Emotional anecdote as the lede before any facts
- Burying key context that undermines the narrative
- "To be sure" paragraph that dismisses counterpoints in a sentence
- Cliffhanger structure designed to provoke anxiety
- Repeated restatement of the same alarming point in different words

## Scoring Guardrails

These prevent the most common scoring errors:

1. **Wire services are not always 1.0.** Wire copy usually scores 1.0–1.5, but it can score higher on opinion-adjacent pieces or when using loaded language. Don't auto-assign low scores based on source reputation.

2. **Center sources can run hot.** Public broadcasters and business news desks have editorial voices. An analysis piece with emotional framing scores 2.5+, not 1.5 just because of the masthead.

3. **Headline alone can push past 3.0.** If the headline contains loaded verbs, catastrophizing, or victory/defeat framing, even if the body is measured, the score reflects that the headline is what most people actually read.

4. **Opinion columns start at 2.5 minimum.** They exist to argue a position. The question is whether they argue with evidence (2.5–3.5) or with emotion (3.5–5.0).

5. **Don't confuse serious topics with hysterical coverage.** A war story can be scored 1.2 if reported factually. A school board story can score 4.5 if reported with outrage. The topic doesn't determine the score. The writing does.

6. **"Both sides" framing isn't automatic Practical.** If an article quotes both sides but gives 80% of space to one, or uses dismissive language for one side ("claimed without evidence"), it's still running hot.

7. **Cumulative fallacy penalty.** One logical fallacy in an otherwise grounded piece might push from 2.0 to 2.3. Three fallacies in the same article suggests a pattern: push harder, to 3.0+.

8. **Sensationalism tax.** If the article makes you feel an emotion BEFORE giving you the facts to justify it, add 0.5 to whatever you'd otherwise score.

## Output Format

For each article, produce:

```
ARTICLE: [headline]
SOURCE: [publication]
TYPE: [news report | analysis | opinion | editorial]

DIMENSION SCORES:
  Headline Framing:      X.X: [one-line justification]
  Language Intensity:     X.X: [one-line justification]
  Source Balance:         X.X: [one-line justification]
  Logical Fallacies:     X.X: [fallacies found, or "none detected"]
  Structural Manipulation: X.X: [one-line justification]

FALLACIES DETECTED: [list each with the specific text that triggers it, or "None"]

FINAL P/H SCORE: X.X
LABEL: [Practical | Grounded | Mixed Signals | Running Hot | Hysterical]
COLOR: [green | lime | yellow | orange | red]

CONFIDENCE: [high | medium | low]
NOTE: [any caveats, e.g. "only headline available, body not analyzed"]
```

## Batch Scoring

When scoring multiple articles on the same story, spread the scores. If 12 articles on the same topic all score between 1.1 and 1.8, something is wrong. A major political story almost always produces coverage spanning at least 2.0 points of range across the full source spectrum. Look harder at headlines, look harder at framing, look harder at what's being left out.

## Examples

All four headlines are invented for illustration.

**Example 1. Score: 1.2 (Practical)**
Headline: "Senate Votes 68-32 to Pass Infrastructure Bill"
Why: States what happened. Number included. Neutral verb. Body follows inverted pyramid, quotes both sponsors and opponents, cites budget office data.

**Example 2. Score: 2.8 (Mixed Signals)**
Headline: "For the Governor, a Promised Jobs Boom Collides With the Cost of the Bridge"
Why: "Collides" is a loaded metaphor. "Promised" implies broken promise. Headline pre-frames the article as a failure narrative. The body may be more measured but the headline does emotional work before the reader starts.

**Example 3. Score: 3.5 (Running Hot)**
Headline: "'Crisis Mayor' Fusses Over Ribbon Cuttings as Flood Damage Mounts"
Why: Scare quotes on "Crisis Mayor" = editorial mockery. "Fusses over ribbon cuttings" is an opinion stated as fact. "Damage mounts" is emotional intensifier. Multiple fallacies: ad hominem (fusses), appeal to emotion (mounting damage), false framing (implying the ribbon cuttings caused the damage).

**Example 4. Score: 4.6 (Hysterical)**
Headline: "Court Ruling Could Doom Global Climate Targets"
Why: "Doom" is catastrophizing. "Could" creates plausible deniability while still triggering fear. Body opens with emotional anecdote, sources almost exclusively from advocacy orgs, opposing legal scholars buried in paragraph 14, uses slippery slope reasoning throughout.
