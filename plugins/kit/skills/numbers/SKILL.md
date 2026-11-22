---
name: numbers
description: Use when adding or changing any number, table or figure in the paper or slides, or when a commit is blocked by the numbers check, in a research-kit project.
---

# Numbers

**Every result is a macro**, including an integer typeset in math: `$N = 1{,}204$` is wrong, `$N = \nObs$` is right. The lint can't see integers in math, so this rule is yours to keep. Never type a result by hand.

## What counts as a result

Always a macro:
- an estimate, standard error, interval, test statistic or p-value;
- a count, sample size, share, rate or percentage computed from data;
- any simulation output (bias, RMSE, coverage, size, power);
- a design setting taken from code: numbers of draws, replications or specifications, a bandwidth, a cutoff.

Not a result, so `%num-ok` at the end of the line is allowed, with approval: a date or year; a conventional threshold stated as a convention (`$\alpha = 0.05$`); a number that is part of a name (a statute, a dataset version); arithmetic in a definition or worked example that doesn't come from data.

## Adding or changing a number

1. **Source.** The value comes from a committed file under `analysis/`, usually a small summary CSV written by code. `numbers_build.py` refuses an untracked or modified source. Commit the source first. Large raw outputs are not sources. Never write the git commit or the run date into a committed result file. Rerunning with unchanged results would then change the file and break any “results unchanged” check.
2. **Entry.** Add or change one entry in the script for the language that computes the value: `analysis/numbers/make_numbers.R` or `analysis/numbers/make_numbers.py`. Each passes its entries to `emit_numbers()`.
   ```r
   list(name = "coverageMain", value = read.csv("analysis/sims/summary.csv")$coverage[1],
        format = "%.2f", src = "analysis/sims/summary.csv")
   ```
   ```python
   dict(name="biasMain", value=float(summary["bias"][0]), format="%.3f", src="analysis/sims/summary.csv")
   ```
   - `name`: letters only, camelCase, starting lowercase, unique across both scripts. The macro name is the claim's stable id, so don't rename a macro that is in use.
   - `value`: read or computed from `src` in the script, never a typed literal.
   - `format`: an `sprintf` format in R, a `%` format in Python. Use number formats (`%.2f`; `%d` only for whole numbers) for numbers, and `%s` only for strings: `%s` prints doubles differently in R and Python.
3. **Generate.** Run:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" numbers_build.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   It runs each language's `make_numbers` script (R with `Rscript`, Python with `uv run --locked`), checks the entries across both, and rewrites `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`) and the generated table in `state/CLAIMS_LEDGER.md` together. On any error, both stay unchanged: read the message and fix the cause. Never run a `make_numbers` script directly; it stops if run outside the builder.
4. **Use** `\coverageMain` in the paper or slides.
5. **Commit.** `numbers.tex` is in the paper repo: commit it there, and push to Overleaf with approval, so the web copy compiles. The `make_numbers` script, the source and the ledger are committed in the code repo.

**Packages the scripts need.** R: `renv::install("<name>")`, then `renv::snapshot()`; Python: `uv add <name>`. Commit the lockfile (`renv.lock` or `pyproject.toml` and `uv.lock`) with the script change.

Tables and figures are written by code into the paper's `tables/` and `figures/` folders, never typed. They sit beside the `generated/` folder that holds `numbers.tex`: `paper/tables/` by default, `paper/draft/tables/` for `numbers_tex: paper/draft/generated/numbers.tex`. `tables/` isn't linted, so every number in a table must come from code.

## When a commit is blocked

The pre-commit hook in each repo (paper: `paper/.lint_baseline`; code: `.lint_baseline_slides`) prints:

```
paper [index]: count=N baseline=B REGRESSION
  <file>:<line>: <token>
  ...
Commit blocked: replace the new numbers with macros, or end the line with %num-ok if the number is not a result.
```

- The list shows **every** bare number in the linted files, old and new. The commit added `N - B` of them; find those in `git diff --cached`.
- Each new one becomes a macro if it is a result, or gets `%num-ok` with approval if it isn't.
- **The ratchet:** a commit that raises the count is blocked, and a commit that lowers it lowers the baseline and stages that file in the same commit. Never edit a baseline by hand, and never commit with `--no-verify`.

To check without committing:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" lint_numbers.py --project "${CLAUDE_PROJECT_DIR}" --gate paper -v
```
(`--gate slides` for the talks.)

## Session-start lines

- `NUMBERS LINT REGRESSION (paper origin): N > B`: an edit on Overleaf added a bare number that hasn't been pulled. Pull, find it, and fix it as above.
- `(paper working tree)` or `(slides working tree)`: local, uncommitted edits added bare numbers.

## False positives

Known lint edge cases and their workarounds are in [KNOWN-ISSUES.md](../../KNOWN-ISSUES.md). Report a false positive that isn't listed there; changing the lint is a kit change.

## Done when
- [ ] Every new or changed result in the paper or slides is a macro, generated from a committed source.
- [ ] `numbers_build.py` exited 0, and `numbers.tex` and the ledger changed together.
- [ ] Every `%num-ok` marks a non-result and was approved.
- [ ] The numbers check passes for each repo touched.
- [ ] Changes were committed, and pushed unless the user declined.

## Stop and ask
- A value can only be typed, not computed from a committed source.
- `numbers_build.py` or `lint_numbers.py` exits 2.
- It's unclear whether a number is a result.
- A false positive isn't listed in `KNOWN-ISSUES.md`.
- A macro in use would have to be renamed.
