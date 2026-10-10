# news-scoring

Two skills that score how a news article is written, not what it covers. Both come from LITMUS, a news-scoring app. Each is a prompt: Claude reads the article text and returns a structured score.

| Skill | Scale | Method |
|---|---|---|
| litmus-editorial-analyzer | 1 to 5, Informing to Manipulating | A checklist. Five sections (source attribution, perspective balance, language intensity, framing devices, tribal signals) are scored 0 to 5 each and the total is converted to the scale. |
| ph-balance-scorer | 1 to 5, Practical to Hysterical | The earlier scale. Five weighted dimensions rated as a whole, with a penalty for each logical fallacy. |

The checklist replaced the tone scale because holistic rating compressed scores into a narrow band and leaned on source reputation. The tone scale stays here for quick reads and for comparison.

The scoring has improved and is imperfect. A score describes technique on the page. It is not a fact-check, and it is not a rating of an outlet.

## What it needs

Nothing to install. There are no scripts. Give the skill the article text; a headline alone gets a lower-confidence score.

## What was removed from the private version

- Example headlines attributed to real news outlets, and two examples that read like real published headlines about a sitting president. Every example headline is now invented, and outlets are described by type (a wire service, a business daily).
- Real people's names inside example headlines.
- Sentences that named real outlets as typical high or low scorers.
- An internal product name in the tone scale's opening line.
- The analyzer's description of itself as the final authority on the method. It defines the scale; it makes no claim about how right a given score is.

## Known limits

- In the analyzer, the band table and the formula disagree at the band edges. The formula `1 + (raw / 25) * 4` puts a raw total of 8 at 2.3, while the table and the output example put a raw total of 8 in the Mixed band (2.5 to 3.4). Decide which one your pipeline follows.
- Scores vary between runs and between models. The batch checks (spread, lean independence, topic independence) are instructions to the model, not code.
- The scales were written for English-language political news in the United States.
