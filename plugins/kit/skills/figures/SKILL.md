---
name: figures
description: Use when designing a new figure for the paper or slides, or reviewing an existing figure or plotting script, in a research-kit project.
---

# Figures

A figure answers three questions, in Tamara Munzner's terms: what the data is (its keys and values, and their types), why the reader looks (the task), and how it is drawn (the idiom: marks, channels and their arrangement). This skill records the three answers in a spec for each figure, checks the design against the idiom catalogue, and only then writes or changes plotting code.

The catalogue in effect is the kit's idioms plus any of your own; `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which idiom <id>` prints the file in effect. Each idiom file says what data it needs, which tasks it serves, which channels carry what, what it hides and how far it scales, citing Munzner's deck pages. Idioms marked `origin: kit` are the kit's own, built in her terms; idioms you add are marked `origin: own`.

## The spec

One file per figure, `notes/figures/<figure>.yml`, named after the figure's file in the paper's figures folder without the extension. A composite figure gets a folder, `notes/figures/<figure>/`, with one spec per panel and a `panel` field in each. An example:

```yaml
figure: effect_by_year
script: analysis/applications/effect_figures.R
title: Estimated effect on the outcome by years since adoption, with 95% intervals
title_in: caption
what:
  items: one estimate per event year
  n_items: 11
  keys: [{name: event_year, type: ordinal, levels: 11}]
  values:
    - {name: estimate, type: quantitative}
    - {name: ci_low, type: quantitative, role: interval}
    - {name: ci_high, type: quantitative, role: interval}
why:
  task: trend
  focus: estimate
  message: The effect is near zero before adoption and grows over the following years.
how:
  idiom: interval-plot
  encode:
    event_year: [{channel: position-common, axis: x}]
    estimate: [{channel: position-common, axis: y}]
  reference:
    - {kind: line, axis: y, at: 0, meaning: no effect}
    - {kind: line, axis: x, at: -0.5, meaning: adoption}
accepted: []
```

Types are categorical, ordinal or quantitative. An attribute the base layout doesn't use takes a role: `interval` for interval bounds, `facet` for small-multiple panels (then `how.facet: {by: <name>, scales: shared}`), `layer` for overlaid series. One attribute may list several channels, such as hue and shape together. Colour is `{channel: colour, colour_scale: categorical | sequential | diverging}`.

## Design a figure

1. **What.** Read the analysis output the figure draws on, and fill `what`: what one item is, how many marks the figure draws, the keys and values with their types and level counts, and the roles.
2. **Why.** Agree with the user on the task, the focus attribute, and a one-sentence message saying what the reader should see. The tasks are compare-values, trend (change along an ordered key, such as time), part-to-whole, relationship, distribution, clusters-outliers, spatial-pattern and lookup. Don't go on without the user's agreement.
3. **Candidates.**
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" figures.py candidates --project "${CLAUDE_PROJECT_DIR}" --task <task> --shape <shape> --key-types <types> --value-types <types>
   ```
   The shape is 0-keys, 1-key or 2-keys (the keys without a role), or geographic. Add --intervals when the values carry intervals, as in an event study or a coefficient plot. Show the user the best two or three, each with what it hides, its scale and its varying channels, and let the user choose.
4. **Spec.** Write the spec, with a `reference` entry and its meaning for each reference mark, such as zero, a treatment date, the diagonal or a threshold. Then run:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" figures.py check --project "${CLAUDE_PROJECT_DIR}" --draft <figure>
   ```
   Fix every error. Fix each warning, or record it under `accepted` with its check, its attribute and the reason, after the user approves.
5. **Code.** Write the plotting code in the project's language: ggplot2 for R, matplotlib for Python.
   - The encoding follows the spec.
   - Each reference mark is drawn, and its meaning is labelled in the image or given in the caption, as its `label_in` says.
   - The figure style in effect applies: read the file that `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which figure-style` prints, in full.
   - The output is a vector PDF in the paper's figures folder.
   - The output path and every size or number the code needs (the printed width, a reference value) are parameters in `analysis/params.yml`, read with `param()`, never typed (`/kit:code`).
   - The title, in the image or as the caption's first clause, names what is plotted, not the finding.
   - Every number in a label or annotation comes from code (`/kit:numbers`).
6. **Render and look.** Run the script, convert the PDF to an image in your scratch folder (`pdftoppm -png -r 150 -singlefile <pdf> <scratch>/<figure>`), and look at it. Then run the check again without `--draft`.
7. **Approve and commit.** Show the user the image and any warnings. After approval:
   - commit the script and the spec in the code repo;
   - commit the figure in the paper repo, and push to Overleaf unless the user declines.

## Critique a figure

1. Start from a figure file or a plotting script. If the figure has no spec, rebuild one from the script and the image, and confirm `why` with the user.
2. Run the checks on it:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" figures.py check --project "${CLAUDE_PROJECT_DIR}" <figure>
   ```
3. Look at the image and go through:
   - the idiom's Hides section and its varying channels (`"${CLAUDE_PLUGIN_ROOT}/bin/kit" which idiom <id>`);
   - the title: does it name what is plotted?
   - reference marks: each drawn, labelled and meaningful, and none missing that the task needs, such as zero for an effect;
   - overplotting, and legibility at the printed size;
   - the figure style in effect.
4. Report the findings, most serious first. Propose each fix as a full before/after of the plotting code and wait for approval, one fix at a time.
5. Carry out approved fixes through design steps 5 to 7.

## Done when
- [ ] The spec exists, and `figures.py check` reports no errors. Each remaining warning is accepted in the spec, with its reason.
- [ ] The user agreed the task and the message, chose the idiom, and approved the rendered image.
- [ ] The script and the spec are committed in the code repo, and the figure in the paper repo.

## Stop and ask
- No analysis output exists for the figure yet.
- No idiom fits. In design, show the closest candidates, or offer a new idiom with `"${CLAUDE_PLUGIN_ROOT}/bin/kit" customize idiom <id>`. In critique, run the checks and say that no idiom fits.
- `figures.py` exits 2.
- The task is not one of the eight above.
- An expressiveness error can't be fixed without changing the message.
