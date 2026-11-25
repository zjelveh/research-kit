# Writing patterns

The kit's default patterns for how paragraphs and sections are built. They describe a common structure for empirical papers that estimate effects. Methods and simulation papers, and fields with other conventions, will depart from the section patterns. To use your own, for example distilled from a model paper in your field, run `kit customize writing-patterns` and edit your copy; your copy then replaces this file. A venue file's required structure wins over a section pattern.

Patterns are defaults for an outline, not templates to fill. An outline may depart from one when the argument needs it, and says why.

## Paragraph patterns

- **Open with the paragraph's job.** The first sentence names what the paragraph does: the result it reports, the threat it answers, the insight it draws. In order, a section's first sentences are the section's argument.
- **Results paragraph.** Open with the table or figure and the finding. Give each estimate in words against its baseline (a percent of the comparison mean, or the level in the reader's units for a headline outcome), at about one estimate per sentence; two estimators' results for the same outcome can share a sentence. State significance in words (statistically significant at conventional levels, not statistically significant). Say what the estimate rules in or out, then end on what it means. Standard errors, p-values and test statistics stay in the tables, and the text names the inference method once where it is introduced, unless a number is itself the point, such as a test that rejects under one method and not another.
- **Synthesis.** After a series of results paragraphs, one paragraph opens with Taken together (or similar) and says what the series shows, pointing back to the results rather than repeating their numbers.
- **Threat and answer.** Each threat to the design is named, then the control or test that answers it, in the same paragraph.
- **Robustness.** One paragraph walks through the checks (First, Second, Finally). It opens with what the checks find, and ends with any plain caution about where the results are sensitive.

An example results paragraph, with invented data. In a paper each number would be a macro.

> Table 3 shows that the cash transfer raised secondary-school enrolment. Children in recipient households were 8 percentage points more likely to be enrolled two years later, against 40 percent of children in comparable households, an increase of a fifth. The gain is statistically significant at conventional levels. Enrolment of their older siblings showed no detectable decline, so the data give no sign that households moved schooling from one child to another. Combined with the attendance results in Table 4, the evidence shows that the transfer raised enrolment with no detectable loss for siblings.

## Section patterns

The usual sequence of paragraphs in each section; each item is one paragraph or a short run of them.

- **Introduction:**
  1. the case: why the question matters, built from what is known;
  2. why the existing evidence falls short: designs, measures, definitions;
  3. this study: what it does differently, and why that answers the shortfall;
  4. a preview of the findings, with their interpretation.
- **Background and expectations:**
  - what prior work found, study by study where few studies exist, then what stands out across them;
  - the mechanisms that could produce an effect;
  - reasons for skepticism;
  - expectations that map each pattern of results to the mechanism it would point to.
- **Data and approach:**
  - the setting and the policy or program;
  - the data, the sample, how each outcome is measured, and its limitations;
  - descriptive comparisons;
  - the identification problem;
  - the design that answers it, with a worked example where it helps;
  - each threat with its answer;
  - the specification and estimation choices.
- **Results:**
  - the main results, one outcome at a time;
  - decompositions, or results over time;
  - a synthesis paragraph;
  - comparisons with simpler estimates, and what they imply about selection;
  - robustness.
- **Discussion:**
  1. a recap: the question, the design in one clause, the main result and its qualification;
  2. the insights, each a finding with what it implies and what the data cannot distinguish;
  3. the contributions, each tied to the prior work it advances;
  4. one main limitation, with its direction where known;
  5. the largest open question: why it matters, and what would answer it;
  6. the close: what the study did and did not show, and what follows.
- **Abstract:** written last, from `notes/argument.md`: the question, the design, the main result with its magnitude, and the interpretation.

### Pre-send checks
The writing skill runs these with the voice file's checks, on outlines and section drafts.

- [ ] Each paragraph opens by naming its job?
- [ ] Results paragraphs: the finding first, estimates in words against the baseline, about one per sentence, significance in words, no standard errors or p-values unless the number is the point?
- [ ] A series of results ends in a synthesis that points back rather than repeating numbers?
- [ ] Each threat named with its answer; robustness in one paragraph?
- [ ] Where the outline departs from a pattern, does it say why?
