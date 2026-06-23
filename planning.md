# TakeMeter — Planning Document
## AI201 · Project 3

---

## Community

**r/leagueoflegends** — one of the largest gaming subreddits (~7 million members), centered on
League of Legends, a competitive team-based game. Discourse covers champion balance, professional
esports, ranked ladder strategy, and patch reactions. The community produces a natural spread of
text types: data-driven balance discussions, heated personal takes on champion design, and pure
emotional reactions to pro-play moments. This makes the analysis / opinion / hype distinction
meaningful and consistently applicable across posts.

---

## Label Taxonomy

### `analysis`
**Definition:** The post makes a structured argument about mechanics, balance, meta, or match
outcomes, supported by specific verifiable evidence (stats, patch notes, replay observations, or
systematic reasoning).

**Examples:**
1. *"Jinx's win rate climbed to 52.4% in Platinum+ this patch despite the Q nerf. The reason is
   the Kraken Slayer interaction — the crit scaling change in 14.1 actually improved her damage
   against tank-heavy comps, which are dominant right now. The nerf hit her in lane, but her
   teamfight upside is stronger."*
2. *"Faker's mid positioning this split has been noticeably more conservative. He's consistently
   giving up kill pressure to enable the bot lane, which makes sense given that Chovy and Ruler are
   the primary carries in this meta. His cs numbers are actually down, but his assist rate is at a
   career high."*

**Uncertain case:** A post that cites one specific stat (e.g., "Yasuo has a 48% win rate, he's
underpowered") but then just argues from that single number without broader reasoning. → See
decision rule below.

---

### `opinion`
**Definition:** The post expresses a personal preference, judgment, or stance — it may reference
specific facts or examples, but the core purpose is to assert a viewpoint rather than build a
systematic argument.

**Examples:**
1. *"Maokai should never have been moved to support. He just doesn't feel right there — top lane
   suits his kit so much better and it kills the fantasy of playing him as a frontline tank."*
2. *"Solo queue is more entertaining than pro play to watch. Pro games are too slow and too
   calculated; I want to see chaos, and ranked delivers that."*

**Uncertain case:** A post that expresses a strong viewpoint but backs it up with a few specific
claims (e.g., lists three champion abilities as evidence for a design complaint). → See decision
rule below.

---

### `hype`
**Definition:** The post is an immediate emotional reaction — excitement, frustration, celebration,
or shock — tied to a specific in-game or esports event, with little to no argumentative content.

**Examples:**
1. *"FAKER JUST 1V5'D IN WORLDS SEMIS I CANNOT BREATHE THIS IS INSANE"*
2. *"Just hit Challenger for the first time after three years of grinding. Actually tearing up right
   now. This game has taken over my life and I don't regret a single second."*

**Uncertain case:** A post that starts as a hype reaction ("that teamfight was INSANE") but then
pivots to a one-sentence observation about why it worked. → See decision rule below.

---

## Decision Rules for Edge Cases

**opinion vs. analysis:**
If the post would read as a complete argument even after removing all emotional/preferential
language, label it `analysis`. If removing the opinion framing leaves only a loose set of
complaints or examples that don't form a cohesive case, label it `opinion`. A single stat cited to
support a rant is still `opinion`; a stat embedded in a multi-step reasoning chain is `analysis`.

**hype vs. opinion:**
If the post is anchored to a specific moment or event (a play, a patch drop, a match result) and
the emotion is the point, label it `hype`. If the post is expressing a general preference or
frustration that isn't tied to an immediate event, label it `opinion`. A post written hours or
days after an event that reflects on it counts as `opinion` even if the language is emotional.

**hype vs. analysis:**
A post can begin with excitement but pivot to explaining *why* something worked. Label based on
the dominant purpose: if the explanation is the main body of the post, it's `analysis`; if the
explanation is one throwaway sentence at the end of a hype post, it's `hype`.

---

## Hardest Anticipated Edge Case

A post like:
> *"Yasuo is the most poorly designed champion in the game — he has too many dashes, a
> point-and-click knockup from his passive, and a 48% win rate floor that still tilts his entire
> team every game."*

This lists three specific claims but the framing is a rant, not an argument. **Decision:** label
`opinion`. The claims serve as rhetorical ammunition, not as premises in a logical structure. If
the post went on to compare Yasuo's kit systematically against design principles or other
champions, it would cross into `analysis`.

---

## Label Summary

| Label      | Core signal                              | Must-have                        | Excluded from                          |
|------------|------------------------------------------|----------------------------------|----------------------------------------|
| `analysis` | Structured argument + verifiable evidence | Evidence forms a reasoning chain | Posts that are primarily venting/reacting |
| `opinion`  | Personal stance, some grounding           | A clear viewpoint being asserted | Posts that are pure in-the-moment reactions |
| `hype`     | Immediate emotional reaction to an event  | Tied to a specific moment        | Posts expressing general preferences  |

---

## Data Collection Plan

**Source:** Reddit posts and top-level comments from r/leagueoflegends, collected via the Reddit
public JSON API (no authentication required for read-only access). I will pull from:
- The **Hot** and **Top (past month)** feeds for a general cross-section of post types
- Patch-day megathreads for hype and reaction content
- Weekly "discussion" and "champion design" threads for opinion and analysis content

**Target distribution:** ~70 `analysis`, ~70 `opinion`, ~70 `hype` (roughly balanced across 210
examples, leaving a buffer above the 200 minimum).

`hype` is the label most likely to be underrepresented in normal post feeds because truly
ephemeral reactions often get less upvotes and are buried quickly. **If `hype` falls below 60
examples after pulling 200 posts**, I will specifically target Worlds/LCS match-day threads and
search for posts containing keywords like "INSANE", "LET'S GO", "I can't believe", and personal
milestone posts (rank-up celebrations).

**Format:** Each example saved as a row in a CSV with columns `text` (the post title + body
concatenated, or the comment text) and `label` (one of `analysis`, `opinion`, `hype`). Posts
longer than ~500 words will be trimmed to the first 300 words to match the input length the model
will see in production.

---

## Evaluation Metrics

**Primary:** Macro-averaged F1 score across all three labels.

Accuracy alone is not sufficient here because the label distribution may not be perfectly balanced
(hype posts are harder to find in normal feeds), and accuracy would hide poor performance on any
one class. Macro F1 weights each class equally regardless of size, so a model that gets `analysis`
right but always fails on `hype` will score poorly — which is the right signal for this task.

**Secondary metrics I will report:**
- **Per-class precision and recall** — to distinguish whether errors are false positives
  (over-labeling a class) or false negatives (missing a class). This matters because the failure
  modes are different: a model that calls everything `analysis` is useless in a different way than
  one that never predicts `hype`.
- **Confusion matrix** — to see which label pairs are hardest to separate. I expect the
  `opinion`/`analysis` boundary to produce the most confusion, and the matrix will confirm or
  deny that.

I will not report AUC-ROC as a primary metric because this is a multi-class classification task
where interpretability of the confusion structure matters more than threshold-independent ranking.

---

## Definition of Success

**Minimum threshold:** Macro F1 ≥ 0.70 on the held-out test set. Below this, the classifier
makes enough mistakes that a community moderator would need to review almost every prediction,
which eliminates the value of automation.

**Target threshold:** Macro F1 ≥ 0.80. At this level, the classifier is accurate enough to be
used as a first-pass filter — surfacing candidate posts for each category — with a human
spot-checking a random 10% sample rather than reviewing everything.

**Baseline comparison:** The zero-shot Groq baseline (llama-3.3-70b-versatile) using my label
definitions as a prompt. If fine-tuned DistilBERT does not exceed the zero-shot baseline by at
least 5 F1 points, the fine-tuning added no meaningful value and the report should explain why
(likely: too little training data, or labels not learnable from surface text patterns alone).

**What would make it not useful even at 0.80:** If the model achieves 0.80 F1 only because it
nails `analysis` (which may have the clearest linguistic fingerprints) while performing near
chance on `hype` — per-class recall below 0.60 on any single class would disqualify it from a
real deployment regardless of overall F1.

---

## AI Tool Plan

### Label stress-testing
Before annotating any examples, I will give Claude my three label definitions and edge case
descriptions and ask it to generate 10 posts that sit at the boundary between two labels. If
Claude produces posts I cannot cleanly classify using my own rules, the definitions need to be
tightened. I will do this for both the `opinion`/`analysis` boundary and the `hype`/`opinion`
boundary. Any posts that expose a gap will trigger a decision rule revision before annotation
begins.

### Annotation assistance
I will use Claude (claude-sonnet-4-6) to pre-label a random 50-example batch after I have
manually labeled the first 100 examples myself. I will provide my full label definitions and
decision rules as the system prompt, then review every AI-suggested label before accepting it.
Pre-labeled examples will be marked with a `source` column value of `ai_prelabeled` in the CSV
for disclosure purposes. The remaining 50+ examples will be labeled manually without AI assistance
to maintain a clean human-labeled baseline.

### Failure analysis
After the model produces its test-set predictions, I will export the wrong-prediction list from
the notebook and give it to Claude with the prompt: "Group these misclassified posts by the type
of error — what patterns do you see?" I will then verify each suggested pattern by reading the
actual posts myself and confirming the pattern holds. I will report only patterns I can verify
with at least 3 concrete examples from the error list.
