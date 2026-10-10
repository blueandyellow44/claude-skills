---
name: litmus-editorial-analyzer
description: "Score news articles on the Litmus Informing-to-Manipulating scale (1–5). Use this skill whenever scoring an article, batch-scoring a set of articles, checking the spread of the scoring engine, or diagnosing why a score seems wrong. Also trigger when building or debugging an AI scoring pipeline, writing prompts for a scoring API, or testing whether the scale produces sufficient variance across sources and political leanings. This skill defines the scale and the method: if there is a question about how a Litmus score is computed, this file is the reference."
---

# Litmus Editorial Analyzer

This skill scores news articles on a 1–5 scale from **Informing** to **Manipulating**. It comes from Litmus, a news-scoring app, and is designed to be used as an AI prompt (fed to Claude or another LLM) that analyzes article text and returns a structured score.

The scoring has improved and is imperfect. A score is a structured reading of how a piece is written. It is not a verdict on whether the piece is true, and two runs on the same article can differ.

The previous scoring system (P/H Balance, the `ph-balance-scorer` skill beside this one) failed because it asked the AI to "rate" articles. That caused score compression (everything clustered at 1.0–1.8), source reputation bias (right-wing sources got flattened scores), and topic confusion (war coverage scored as "hysterical" regardless of writing quality). This skill was built to address those failures with a **checklist-based detection method**: the AI scans for specific manipulation signals, counts them, and computes a score from the findings. No vibes. No gestalt ratings. Count the signals, compute the score.

## The Scale

| Score | Label | What it means |
|---|---|---|
| 1.0–1.4 | Informing | Pure reporting. Facts are sourced and attributed. Multiple perspectives represented. The reader is given information and trusted to draw their own conclusions. |
| 1.5–2.4 | Mostly Informing | Facts are central but the writer makes editorial choices: selective emphasis, a pointed headline, one perspective gets more space. Still primarily informational. |
| 2.5–3.4 | Mixed | Equal parts information and persuasion. The reader gets facts but has to actively separate them from framing. The article has a clear point of view that shapes the presentation. |
| 3.5–4.4 | Mostly Manipulating | Facts are present but secondary to emotional framing. The article uses tribal signals (us-vs-them language, emotional manipulation, conformity pressure) to shape the reader's reaction before they encounter the evidence. |
| 4.5–5.0 | Manipulating | Tribal content in a news format. Cherry-picked evidence, emotional language throughout, logical fallacies, missing context that would undercut the thesis. Written for people who already agree. |

## The Detection Checklist

Score an article by scanning for these signals. Each section produces a subscore. The final score is computed from the subscores.

### Section A: Source Attribution (0–5 points)

Count how many claims in the article are attributed to named, verifiable sources.

| Finding | Points |
|---|---|
| All major claims attributed to named sources with credentials or position | 0 |
| Most claims attributed, 1–2 use vague attribution ("officials say," "sources close to") | 1 |
| Mix of attributed and unattributed claims | 2 |
| Most claims unattributed or use weasel phrases ("some say," "many believe," "critics argue") | 3 |
| Major claims are presented as fact with no attribution at all | 4 |
| Claims are actively misleading about their sources (misquotes, out-of-context quotes, fabricated consensus) | 5 |

### Section B: Perspective Balance (0–5 points)

Check whether the article represents more than one perspective on the issue.

| Finding | Points |
|---|---|
| Multiple substantive perspectives presented with fair space and genuine engagement | 0 |
| Multiple perspectives present but one gets significantly more space or more sympathetic framing | 1 |
| A second perspective is mentioned but dismissed, strawmanned, or given a single sentence | 2 |
| Only one perspective is present; the opposing view is referenced only as something to refute | 3 |
| Only one perspective exists; the article assumes the reader already agrees | 4 |
| The article actively demonizes people who hold the opposing view: they are stupid, evil, or dangerous | 5 |

### Section C: Language Intensity (0–5 points)

Scan the article for emotionally loaded language choices. Focus on VERBS and ADJECTIVES, not the topic.

Important: The subject matter does not determine the score. A factual report about a bombing that says "6 killed in airstrike" uses neutral language about a violent topic. A sensationalized piece about a school board meeting that says "parents SLAMMED the radical agenda" uses loaded language about a mundane topic. Score the WRITING, not the SUBJECT.

| Finding | Points |
|---|---|
| Neutral, precise language throughout. Verbs are descriptive ("said," "reported," "announced"). Adjectives are factual ("estimated," "proposed," "bipartisan"). | 0 |
| Mostly neutral with 1–2 loaded word choices ("slammed," "gutted," "bombshell") | 1 |
| Regular use of loaded verbs and adjectives that push the reader toward a specific emotional reaction | 2 |
| Emotional language is the dominant register. Loaded verbs in most paragraphs. Adjectives frequently editorialize. | 3 |
| Language is consistently inflammatory. Metaphors of war, disease, or catastrophe applied to political disagreements. | 4 |
| The article reads like advocacy. Every sentence is engineered for emotional impact. Sarcasm, contempt, or mockery directed at political opponents. | 5 |

### Section D: Framing Devices (0–5 points)

Check for structural manipulation: how the article is organized to lead the reader to a predetermined conclusion.

| Finding | Points |
|---|---|
| Inverted pyramid or neutral structure. The most important facts come first. Context is provided without editorializing. | 0 |
| Headline is slightly more dramatic than the article supports, but the body is factual | 1 |
| The article uses selective ordering: favorable evidence first, unfavorable evidence buried or absent | 2 |
| The article opens with an emotional anecdote or provocative claim, then backfills with selective evidence | 3 |
| The article uses false equivalence, false dilemma, or cherry-picked statistics to support a predetermined conclusion | 4 |
| The entire structure is designed to manipulate: misleading headline, emotional opening, cherry-picked evidence, straw man opposition, call to action or tribal conclusion | 5 |

### Section E: Tribal Signals (0–5 points)

This is what makes Litmus different from generic "media bias" scores. Tribal signals are the specific techniques that turn journalism into team sport content. Scan for:

- **Us-vs-them framing**: Does the article divide the world into the good team and the bad team? ("Conservatives believe in freedom" / "The radical left wants to destroy...")
- **In-group assumptions**: Does the article assume the reader already agrees? ("As we all know..." / "Any reasonable person can see...")
- **Conformity pressure**: Does the article shame or mock people who disagree? ("Only a fool would believe..." / "The so-called 'experts'...")
- **Identity over evidence**: Does the article appeal to group identity rather than evidence? ("Real Americans know..." / "If you care about justice, you must...")
- **Enemy construction**: Does the article construct a villain, meaning not a person with a different view but an enemy to be opposed?

| Finding | Points |
|---|---|
| No tribal signals. The article treats the topic as a matter of facts, trade-offs, and legitimate disagreement. | 0 |
| 1 minor tribal signal (a single us-vs-them phrase or a mild in-group assumption) | 1 |
| 2–3 tribal signals present but not dominant. The article has substantive reporting alongside tribal framing. | 2 |
| Tribal signals are frequent. The article consistently frames the issue as a contest between good and evil rather than a policy debate. | 3 |
| Tribal signals are pervasive. The article is primarily organized around in-group validation and out-group demonization. Evidence is selected to reinforce tribal identity. | 4 |
| The article is pure tribal content. Every element (headline, structure, language, sourcing) serves the tribe. Dissent is not just absent but implicitly punished. | 5 |

## Computing the Final Score

1. Score each section A through E (0–5 each)
2. Sum the raw scores (0–25 possible)
3. Convert to the 1–5 scale:

| Raw Total (0–25) | Final Score | Label |
|---|---|---|
| 0–3 | 1.0–1.4 | Informing |
| 4–7 | 1.5–2.4 | Mostly Informing |
| 8–12 | 2.5–3.4 | Mixed |
| 13–18 | 3.5–4.4 | Mostly Manipulating |
| 19–25 | 4.5–5.0 | Manipulating |

More precisely: `final_score = 1 + (raw_total / 25) * 4`, rounded to one decimal place. This produces a linear mapping from 0→1.0 to 25→5.0.

## Critical Rules

These rules exist because the previous scoring system violated them and broke.

### Rule 1: Score the Writing, Not the Source
Do not let your knowledge of the source influence the score. A wire service can publish a manipulative analysis piece. A partisan outlet can publish a straight wire report or a well-sourced investigation. Score what is on the page, not what you expect from the masthead. If you catch yourself thinking "this is that outlet, so it's probably a 3+," stop and re-read the actual text.

### Rule 2: Score the Writing, Not the Topic
A factual report about war, terrorism, mass shootings, or pandemics is NOT manipulative because the subject is disturbing. "6 killed in airstrike, officials say" is a 1.0 article. "Catastrophic airstrike DECIMATES community as politicians do NOTHING" is a 4.0+ article. Same event, completely different writing. The checklist forces you to score language, not subject matter. Follow it.

### Rule 3: Don't Compress
The previous system scored 90% of articles between 1.0 and 1.8. That's useless. The checklist is designed to spread scores. Use the full range. If you score 10 articles from different sources and they all land between 1.0 and 2.5, something is wrong: re-read with fresh eyes and look harder for the signals in Sections C, D, and E. Conversely, if everything scores above 3.5, you're being too aggressive.

### Rule 4: Opinion Is Not Manipulation
A clearly labeled opinion piece or editorial that argues a position with evidence, acknowledges counterarguments, and uses the author's name and credentials is NOT inherently manipulative, even if you disagree with the conclusion. Manipulation is about technique (tribal signals, emotional language, missing context, false framing), not about having a point of view. A well-argued opinion piece might score 2.0–2.5. A poorly argued one that uses tribal tactics scores 4.0+.

### Rule 5: Political Neutrality Is Mandatory
The score must be independent of political lean. This means:
- Conservative and liberal sources must be scored by the same criteria
- Direct, assertive language is not the same as manipulative language
- Traditional/religious framing is not inherently tribal (unless it's used to construct us-vs-them)
- Progressive/academic framing is not inherently neutral (it can be deeply tribal)
- If your scores consistently correlate with political lean (all right-wing sources score high, all left-wing sources score low, or vice versa), your scoring is biased

## Reference Headlines

Use these to check that the scoring engine spreads scores the way the scale intends. Every headline and outlet type below is invented for illustration: five ways of covering the same imaginary court ruling. If your scores do not approximate these ranges, the prompt or the pipeline needs adjustment.

### Should score 1.0–1.4 (Informing)
**A wire service**: "High Court Rules 5-4 to Limit Agency Authority Over Carbon Emissions"
- Attribution: Named justices, specific vote count, direct quotes from opinion
- Balance: Majority and dissent summarized
- Language: Neutral throughout
- Framing: Inverted pyramid
- Tribal: None

### Should score 2.0–2.5 (Mostly Informing)
**A business daily's news section**: "Court Reins In Regulator, Bolstering Business Certainty"
- Attribution: Named sources, industry and environmental groups quoted
- Balance: Both sides present, business perspective gets more space
- Language: "Bolstering" and "reins in" show mild editorial lean in headline
- Framing: Slightly favorable to business perspective
- Tribal: None

### Should score 2.8–3.4 (Mixed)
**A national daily's news analysis**: "Top Court Strips Regulator of Key Climate Powers in Blow to White House Agenda"
- Attribution: Good sourcing
- Balance: Multiple views but environmentalist framing dominates
- Language: "Strips," "blow" are moderately loaded words
- Framing: Headline is more dramatic than body supports
- Tribal: Mild. Implies the ruling is a loss for "the good side"

### Should score 3.8–4.4 (Mostly Manipulating)
**An opinion piece presented as analysis**: "Major Victory for Energy Independence as Court Smashes Regulatory Overreach"
- Attribution: Selective quoting of supporters
- Balance: Opposition dismissed in one paragraph
- Language: "Victory," "smashes," "overreach" are heavily loaded
- Framing: Celebratory structure, evidence selected to support conclusion
- Tribal: Strong. "We won," and the opposition is overreaching government

### Should score 4.5–5.0 (Manipulating)
**A partisan advocacy blog**: "Corrupt Court Sells Out Our Children's Future to Billionaire Donors' Demolition Scheme"
- Attribution: Conspiracy framing, unnamed "dark money" sources
- Balance: None. The opposing view is presented as corruption
- Language: "Corrupt," "sells out," "demolition scheme" are pure inflammatory
- Framing: Entire structure designed for outrage
- Tribal: Maximum. Readers who disagree are complicit in corruption

## Output Format

When scoring an article, return:

```json
{
  "score": 2.8,
  "label": "Mixed",
  "sections": {
    "source_attribution": { "score": 1, "note": "Most claims attributed, 2 use 'officials say'" },
    "perspective_balance": { "score": 2, "note": "Environmental view gets one dismissive sentence" },
    "language_intensity": { "score": 2, "note": "'Strips' and 'blow' in headline, body mostly neutral" },
    "framing_devices": { "score": 2, "note": "Headline more dramatic than body supports" },
    "tribal_signals": { "score": 1, "note": "Mild implication that ruling is a setback for progress" }
  },
  "raw_total": 8,
  "political_lean": "Center-Left",
  "source": "Example Daily",
  "headline": "Top Court Strips Regulator of Key Climate Powers in Blow to White House Agenda"
}
```

## Batch Scoring Rules

When scoring multiple articles (e.g., 10+ articles for a daily feed):

1. **Spread check**: After scoring all articles, verify the scores span at least 2.5 points across the batch. If they don't, re-score the highest and lowest: you're probably compressing.
2. **Lean independence check**: Group scores by political lean. If the average score for right-leaning sources is more than 1.0 points different from left-leaning sources, check for political bias in your scoring.
3. **Topic independence check**: If all articles about the same topic (e.g., a shooting, a war) cluster above 3.0, you're probably scoring the topic, not the writing. Re-read Rule 2.
