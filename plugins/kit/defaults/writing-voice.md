# Base voice

The kit's default voice for manuscript prose and slide text. To change it, run `kit customize writing-voice` and edit your copy; your copy then replaces this file.

### Register
- Matter-of-fact and understated: state findings plainly, without amplification.
- Umbrella test: does the word or sentence carry a fact, or ask the reader to feel something? If the second, cut it.
- No dramatic beats or reveals: no short sentence whose job is rhythm or suspense.
- No figurative or narrative register: no concealment-revelation words (hidden, surfaced, into the open, all along) and no institutions with wants or impulses.
- No hedging about the paper itself ("this paper attempts to", "we hope to show").
- Use "we" for what the paper does (we estimate, we exclude), not as throat-clearing ("we argue that it is important to note").
- No rhetorical questions. A direct question may state the paper's own research question.

### Claims
- **(hard rule)** Claims stop at what was measured: "no detectable increase", not "no cost". A result observed only on a selected subsample says so.
- **(hard rule)** State a mechanism by enumerating what happened, never with a vague stand-in ("its role") or imputed purpose ("was for").
- Name what was measured, not the construct it stands in for; use the construct's name for theory, and only after the measured version is stated.
- Label every comparison causal or descriptive in the sentence that introduces it; say why a descriptive one falls short.
- "Associated with" is not "caused". Acknowledge a limit once, without over-hedging.
- Name statistical relationships precisely, with direction: predicts, is associated with, is higher for, has a coefficient of. Not loose stand-ins: rises with, tracks, follows, moves with, responds to, reflects, is tied to. "Is sensitive to" only in its technical sense (how much a result changes when an input changes). No signature, fingerprint or hallmark.
- State the claim, then support it; no deferring connectives (hints at, points to, gestures toward, speaks to, opens the door to).

### Results
- **(hard rule)** Every empirical claim carries its magnitude, as a macro; heterogeneity claims carry the test, its value and the effect size. A descriptor may frame a number, never replace it.
- Report a result as estimate, then magnitude in the reader's units with the baseline, then interpretation. Levels, direction and endpoints, not "fell sharply".
- Open each robustness paragraph with that check's finding, not "the result holds".
- The abstract's hedging matches the body's.
- **(hard rule)** Figure and table titles, and a caption's first clause, name what is plotted, not the finding. Fix the title in the plotting script.

### Sentences
- Em-dashes only for short asides (3–8 words), and sparingly.
- No abstraction doing a human action ("the literature wants", "the reform decided"). Estimators, tests and quantities may be subjects ("the estimator converges").
- Use "it" only when the antecedent is the immediately preceding subject and no other singular noun competes; otherwise name the noun.
- No stacks of three or more modifiers before a noun; unpack them into a clause.
- One idea per sentence. Split a sentence that hangs a comparison or a chain of qualifiers off one noun: first say who did what, then give the comparison its own sentence, naming both groups. Not "The district also kept on the waiting list many applicants with higher entrance scores than those admitted by lottery" but "The district admitted some applicants by lottery. It kept others on the waiting list. Many of the applicants it kept had higher entrance scores than the applicants it admitted."
- No padded lists of three: a list is allowed only when each item is a distinct fact the reader needs.

### Words
- Plain reporting verbs: found, reported, documented, showed, estimated.
- No journalistic words: revealed, discovered, troubling, striking, alarming.
- No intensifiers or significance flags: truly, profound, remarkable, critical, crucial, fundamental, pivotal, striking, notable, important, key. "Significant" only in its statistical sense.
- No honesty qualifiers (honestly, candidly, frankly) and no finding-intensifiers (genuine, real, true).
- No loaded adverbs (quietly, openly, merely, simply, starkly).
- No LLM tics: delve, leverage, facilitate, endeavor, "methodology" as filler, "it is important to note", "it is worth mentioning".
- No names from the code (variables, files, functions) anywhere paper-facing: body, captions, notes, axis labels, appendix. Translate at the source.

### Pre-send checks
The writing skill runs these on every paragraph before showing it.

- [ ] Every word and sentence carries a fact: no dramatic beat, figurative register or loaded adverb?
- [ ] No intensifiers, significance flags, honesty qualifiers, journalistic words or LLM tics?
- [ ] No hedging about the paper itself, and no rhetorical question?
- [ ] No names from the code?
- [ ] (hard rule) Every empirical claim carries its magnitude, as a macro?
- [ ] (hard rule) Claims stop at what was measured, with selection flagged?
- [ ] (hard rule) Mechanisms enumerated, with no imputed purpose?
- [ ] (hard rule) Figure and table titles name what is plotted?
- [ ] Every comparison labelled causal or descriptive; statistical relationships named precisely, with direction?
- [ ] Results ordered estimate, magnitude with baseline, interpretation; abstract hedged like the body?
- [ ] Em-dashes only for short asides; no abstraction doing a human action?
- [ ] Every "it" has one clear antecedent; no stacks of 3+ modifiers; one idea per sentence, with no comparison or qualifier chain hung off a noun; no padded list of three?
