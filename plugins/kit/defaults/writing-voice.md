# Base voice

An example voice for manuscript prose and slide text. It shows what a voice file holds, and the kit uses it until you replace it with your own: run `kit customize writing-voice` and edit your copy; your copy then replaces this file. How paragraphs and sections are built is a separate default, `writing-patterns`.

### Register
- Matter-of-fact and understated: state findings plainly, without amplification. Each word and sentence carries a fact; cut what only asks the reader to feel something.
- No dramatic beats or reveals: no short sentence whose job is rhythm or suspense.
- Literal register: report what the data show, not a story of discovery, and give institutions and abstractions no wants or decisions. Estimators, tests and quantities may be subjects ("the estimator converges").
- No hedging about the paper itself ("this paper attempts to", "we hope to show").
- Use "we" for what the paper does (we estimate, we exclude), not as throat-clearing.
- No rhetorical questions. A direct question may state the paper's own research question.

### Claims
- **(hard rule)** Claims stop at what was measured: "no detectable increase", not "no cost". A result observed only on a selected subsample says so.
- **(hard rule)** Every empirical claim carries its magnitude, as a macro, in the claim's home: the place `notes/argument.md` gives it, or, without an argument file and in slides and captions, the claim's first statement in that document. A recap or back-reference may point to the home instead of repeating the number. A heterogeneity claim names its test in words; the test statistic stays in the table unless the number is itself the point.
- **(hard rule)** Figure and table titles, and a caption's first clause, name what is plotted, not the finding. Fix the title in the plotting script.
- State a mechanism by saying what happened, not with a vague stand-in such as "its role".
- Name what was measured, not the construct it stands in for; use the construct's name for theory, and only after the measured version is stated.
- Label every comparison causal or descriptive in the sentence that introduces it, and say why a descriptive one falls short. "Associated with" is not "caused"; acknowledge a limit once, without over-hedging.
- Name statistical relationships precisely, with direction (predicts, is associated with, has a coefficient of), not with loose stand-ins (tracks, moves with, reflects).
- The abstract's hedging matches the body's.

### Words
- Plain reporting verbs: found, reported, documented, showed, estimated.
- None of these: journalistic words (revealed, striking, alarming); intensifiers (truly, remarkable, crucial); common LLM tics (delve, leverage, "it is important to note"). "Significant" only in its statistical sense.
- No names from the code (variables, files, functions) anywhere paper-facing: body, captions, notes, axis labels, appendix. Translate at the source.

### Pre-send checks
The writing skill runs these on section drafts and line edits before showing them; the patterns file's checks run on outlines and sections.

- [ ] (hard rule) Claims stop at what was measured, with selection flagged?
- [ ] (hard rule) Every empirical claim carries its magnitude, as a macro, in its home, and recaps point back to it?
- [ ] (hard rule) Figure and table titles name what is plotted?
- [ ] No intensifiers, journalistic words or LLM tics, and no names from the code?
- [ ] No dramatic beat, story of discovery, hedging about the paper or rhetorical question?
- [ ] Every comparison labelled causal or descriptive; mechanisms stated as what happened; statistical relationships named precisely, with direction; the abstract hedged like the body?
