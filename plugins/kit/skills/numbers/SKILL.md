---
name: numbers
description: Use when adding or changing any number, table or figure in the paper or slides, or when a commit is blocked by the numbers or table check, in a research-kit project.
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
   list(name = "coverageMain", value = read.csv(param("sims_summary"))$coverage[1],
        format = "%.2f", src = param("sims_summary"))
   ```
   ```python
   dict(name="biasMain", value=float(summary["bias"][0]), format="%.3f", src=param("sims_summary"))
   ```
   The source's path is a parameter in `analysis/params.yml` (`/kit:code`), never typed: the scripts load `param()` at the top. A script made before the parameter files needs `source("analysis/params.R")` (R) or `sys.path.insert(0, "analysis")` and `from params import param` (Python) added after its emit lines; if `analysis/params.yml` is missing, run `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-params` first.
   - `name`: letters only, camelCase, starting lowercase, unique across both scripts. The macro name is the claim's stable id, so don't rename a macro that is in use.
   - `value`: read from `src`, or computed from it by a library function, never a typed literal. The numbers script is a driver like any other (`/kit:code`): it defines no functions, so a helper such as a percent formatter belongs in the library.
   - `format`: an `sprintf` format in R, a `%` format in Python. Use number formats (`%.2f`; `%d` only for whole numbers) for numbers, and `%s` only for strings: `%s` prints doubles differently in R and Python.
3. **Generate.** Run:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" numbers_build.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   It runs each language's `make_numbers` script (R with `Rscript`, Python with `uv run --locked`), checks the entries across both, and rewrites `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`) and the generated table in `state/CLAIMS_LEDGER.md` together. On any error, both stay unchanged: read the message and fix the cause. Never run a `make_numbers` script directly; it stops if run outside the builder.
4. **Use** `\coverageMain` in the paper or slides.
5. **Commit.** `numbers.tex` is in the paper repo: commit it there, and push to Overleaf with approval, so the web copy compiles. The `make_numbers` script, the source and the ledger are committed in the code repo.

**Packages the scripts need.** R: `renv::install("<name>")`, then `renv::snapshot()`; Python: `uv add <name>`. Commit the lockfile (`renv.lock` or `pyproject.toml` and `uv.lock`) with the script change.

Tables and figures are written by code into the paper's `tables/` and `figures/` folders, never typed. They sit beside the `generated/` folder that holds `numbers.tex`: `paper/tables/` by default, `paper/draft/tables/` for `numbers_tex: paper/draft/generated/numbers.tex`. `tables/` isn't linted for bare numbers, so every number in a table must come from code. Designing a figure, or reviewing one, goes through `/kit:figures`.

**Table checks.** The paper repo's hook also checks the tables the manuscript inputs (`tabular`, `tabular*`, `tabularx` and `longtable`), and every `.tex` file directly in `tables/`:
- **A negative number printed with a hyphen** in a cell (`-0.18`): LaTeX sets it as a hyphen, not a minus. The code that writes the table prints `$-$0.18` or `\ensuremath{-}0.18`. siunitx `S` and dcolumn `D` columns set their own minus, and so do `\num{}` and its relatives.
- **A generated macro whose value is a negative number written with a hyphen.** `numbers_build` writes `numbers.tex` with a real minus, so rerun it; a project's own macro file is fixed in the code that writes it.
- **Stars without a legend,** and **a legend whose thresholds differ** from what most of the paper's tables say.

A value that rounds to zero printed with a real minus (`$-$0.0`) is a warning, not a block; printed with a hyphen (`-0.0`) it is also a hyphen-for-minus finding, which blocks. Drop the sign on a point estimate, and on an interval bound show more decimals (`$-$0.04`), since the sign says the interval reaches below zero. `numbers.tex` drops the sign of a value that rounds to zero, so give an interval bound's macro enough decimals in its format. A star legend typed in the manuscript's own files is read by the numbers check too, so its thresholds need `%num-ok`, or write the legend in the table file. A line whose comment starts with `%table-ok: <reason>` drops that line's findings; `%legend-ok: <reason>` anywhere in a table drops its legend findings, for a legend given elsewhere. The table check has its own ratchet and baseline, `.lint_baseline_tables`, beside the numbers baseline; the first time the hook runs without one, it starts from the last commit's count. `lint_tables.py --report` lists where the paper mixes two forms of one thing (p-values with and without a leading zero, captions with and without a final period, thousands separators, a talk's star thresholds against the paper's). Which form to use is the project's choice; the report only shows the mix.

## Writing tables

Tables are written with the kit's table writer, which passes these checks by construction: every number through one formatter (a real minus, no sign on a value that prints as zero, the paper's separators), stars and their legend from the same thresholds, p-values never printed as zero or on the other side of a threshold, an interval bound that would print as zero given decimals instead.
- **Adding it:** `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-tables r|python --stars '<marker>:<threshold>,...'` (or `--no-stars`) copies `tex_tables.R` or `tex_tables.py` into the library and appends the `table_*` settings `analysis/params.yml` lacks, in one commit. Before running it, ask the user for the star rule, unless `analysis/params.yml` already sets `table_star_thresholds` and `table_star_markers` (adding the second language's writer, say: then run it without a star flag) or `kit which table-style` prints a personal file that sets them. When the paper already has tables with stars, read their legends and propose the rule most of them use, so the first new table doesn't disagree. With several library folders it asks for `--into <folder>`. The project then owns the file: edits are fine, and a rerun never overwrites them.
- **Using it:** a driver builds the paper's style once and passes it to every call: `style <- table_style(param)` (Python: `style = table_style(param)`), then `tex_number()`, `star_marker()`, `p_cell()`, `se_cell()`, `interval_cell()`, `table_row()`, `header_band()`, `tex_table()` and `write_tex()` with the output path from `param_path()`. Passing `param` to the writer works in a package too, whose own code never calls `param("x")`. Rows are built in the driver with `table_row()` over the results, in an anonymous function or a loop; a helper the driver defines is a code-gate finding, so a row builder the paper's tables share goes in the library. `tex_table()` with a caption writes the whole float; without one, the table and its notes, for a manuscript that holds the caption and `\input`s the file inside its own float.
- **The paper's style** is the `table_*` settings in `analysis/params.yml`, changed there with approval like any parameter. A table that needs another value overrides it by name (`table_style(param, size = "scriptsize")`). A number typed in a driver is a code-gate finding, so a numeric override (`decimals = 4`) is a parameter of its own named for the table (`balance_table_decimals`, not a `table_` name), with a comment saying why; so is a string override that several tables share.
- The paper loads `booktabs` (and `pdflscape` for a landscape table).

## When a commit is blocked

In the code repo, the hook runs the code check first: a block that starts `code gate: N findings` is about the code (typed values, functions in pipeline scripts, near copies, parameters, or archived R code without its `.renvignore`), and `/kit:code` says what to do. The numbers check follows. The pre-commit hook in each repo (paper: `paper/.lint_baseline`; code: `.lint_baseline_slides`) prints:

```
paper [index]: count=N baseline=B REGRESSION
  <file>:<line>: <token>
  ...
Commit blocked: replace the new numbers with macros, or end the line with %num-ok if the number is not a result.
```

- The list shows **every** bare number in the linted files, old and new. The commit added `N - B` of them; find those in `git diff --cached`.
- Each new one becomes a macro if it is a result, or gets `%num-ok` with approval if it isn't.
- **The ratchet:** a commit that raises the count is blocked, and a commit that lowers it lowers the baseline and stages that file in the same commit. Never edit a baseline by hand, and never commit with `--no-verify`.

In the paper repo the table check runs in the same hook and prints its own block:
```
tables [index]: count=N baseline=B REGRESSION
  tables/table_main.tex:14: hyphen for minus: -0.182
  sections/results.tex:120: stars without a legend: **, ***
  warning: tables/table_main.tex:20: negative zero: $-$0.0 (...)
Commit blocked: print negatives with a real minus ($-$ or \ensuremath{-}) in the code that writes the table, give every star a legend, or end the line with %table-ok: <reason> (%legend-ok: <reason> for a legend given elsewhere).
```
A legend finding is reported at the `\begin` line of the table's outermost float. Both checks always run, the commit is blocked if either fails, and neither baseline moves unless both pass. Fix each new finding in the code that writes the table (or rerun `numbers_build`), or end the line with `%table-ok: <reason>` with approval.

**A commit of named paths** (`git commit <paths>`) runs the hook on git's temporary index, so a baseline the hook sets or lowers is committed but the real index keeps the old one. After such a commit whose hook printed `baseline set` or `baseline lowered`, run `git -C <paper> add .lint_baseline_tables` (and `.lint_baseline` for `paper: baseline lowered`), so the next commit is checked against the new baseline.

To check without committing:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" lint_numbers.py --project "${CLAUDE_PROJECT_DIR}" --gate paper -v
```
(`--gate slides` for the talks.) The table check on its own, with every finding:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" lint_tables.py --project "${CLAUDE_PROJECT_DIR}" -v
```

## Session-start lines

- `NUMBERS LINT REGRESSION (paper origin): N > B`: an edit on Overleaf added a bare number that hasn't been pulled. Pull, find it, and fix it as above.
- `(paper working tree)` or `(slides working tree)`: local, uncommitted edits added bare numbers.

## False positives

Known lint edge cases and their workarounds are in [KNOWN-ISSUES.md](../../KNOWN-ISSUES.md). Report a false positive that isn't listed there; changing the lint is a kit change.

## Done when
- [ ] Every new or changed result in the paper or slides is a macro, generated from a committed source.
- [ ] `numbers_build.py` exited 0, and `numbers.tex` and the ledger changed together.
- [ ] Every `%num-ok` marks a non-result and was approved.
- [ ] The numbers check passes for each repo touched, and the table check for the paper.
- [ ] Changes were committed, and pushed unless the user declined.

## Stop and ask
- A value can only be typed, not computed from a committed source.
- `numbers_build.py`, `lint_numbers.py` or `lint_tables.py` exits 2.
- It's unclear whether a number is a result.
- A false positive isn't listed in `KNOWN-ISSUES.md`.
- A macro in use would have to be renamed.
