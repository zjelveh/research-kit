# Known issues

These are rare edge cases that have been accepted rather than fixed. The bar for fixing something is a real bug: valid LaTeX that blocks a commit, or a hand-typed result that slips through. Everything below falls short of that bar; most cases have a workaround (`%num-ok`).

## Numbers lint (`plugins/kit/scripts/lint_numbers.py`)

### False positives (fix by ending the line with `%num-ok`)

- **TeX dimensions in prose** count as numbers: `\fontsize{10}{12}`, `\captionsetup{skip=5pt}`.
- **Colour, width and layout arguments of commands outside the policy tables** count as numbers: `\cellcolor{gray!6}`, tabularray `tblr` keys, `\newgeometry{margin=1in}`, `\animategraphics`.
- **`\addplot` outside an `axis` environment** counts as numbers.
- **`2SLS`** counts as a number. The refined name rule exempts only digits preceded by a letter and the ordinal or plural suffixes st, nd, rd, th and s.
- **`thebibliography` / `\bibitem` text** is linted. Policy item P12 (skip it) was not adopted.
- **Stargazer-style cells and notes** are flagged, for example `p$<$0.1`. That is correct under the rule. Whether generated table files are linted at all depends on `lint.paper.globs`.

### False negatives (accepted)

- **Optional arguments of listed commands** are never linted, as the spec requires. Examples: `\item[0.94]`, `\section[Short 0.5]`, and the notes in cite commands.
- **`\item` followed by a newline and then `[..]`** treats the bracket as the item label, the same way LaTeX does.
- **Integers in math** are ignored, as the spec requires, for example `$N = 1{,}204$`. The numbers skill states the rule that every result is a macro.
- **`1e-5` in math** is ignored because it has no decimal point. `2.5e-3` is flagged.
- **Decimals with an ordinal or plural suffix** count as names: "97.5th percentile", "a 0.5s delay".
- **Version-like tokens after a letter** count as names, for example `v2.1`.
- **`\code{}` is always read raw.** In a non-JSS paper that defines its own `\code`, numbers inside it are hidden.

### Valid LaTeX that still raises (rare; usually preamble-only)

- **`$$` inside a table cell**, for example `$$-$0.003$`. Inside a cell TeX reads this as an empty formula followed by a new one.
- **Known commands that really are missing an argument**, for example a `\section` with nothing after it at the end of a file. This is typical of a preamble, which is never scanned. A command passed as a token in braces, as in `\patchcmd{\section}…`, is handled.
- **URL commands from other packages** (`\doi`, `\nolinkurl`, `\path`, `\qrcode`) are not read raw, so a `%` inside them raises.

### Diagnostics

- The "`\[` inside math" error does not name the line where the open math began.

### Behaviour notes

- In `\textcolor` and `\hyperref`, the text argument keeps the surrounding mode, so it stays math inside math.

## Numbers lint CLI (`lint_numbers.py --gate …`)

- `--write-baseline` ignores `--git-ref` and `--index` and always counts the working tree.
- `git()` calls inherit `GIT_INDEX_FILE` and `GIT_DIR`. The checks rely on this: inside a hook they read the commit's own index, so a commit of named paths, or one made from a worktree, checks the files that commit stages.
- A new project's first commit must stage `.lint_baseline` before the hook runs, because in index mode the baseline is read from the index. The scaffold already does this.

## Small checks

- `check_stale.py`: a blank or whitespace-only phrase is reported as found everywhere instead of raising a usage error.
- `check_bib.py`: citation keys are compared case-sensitively.
- `notation_tex.py`: a macro name that LaTeX already defines (for example `\theta`) passes, then fails when the paper compiles. The separator row is not validated.
- `decisions_index.py`: a `### D-…` line inside a fenced code block is treated as a decision heading.
- `check_pointers.py`: a bare filename such as `numbers.tex` is resolved against the project root only. Use full relative paths.

## Scaffold (`scaffold.py`)

- A failed `attach-paper` leaves `research.yml` with the detected branch. Rerunning `attach-paper` sets it again, so this is harmless.
- A rerun reuses a kept clone only if its origin URL matches the given one exactly; the same project given as a different URL spelling (a trailing `.git`) is refused as "already exists".
- A branch name that YAML reads specially (`yes`, `null`, `123`) would be written without quotes.
- Group write is not enforced: `set_group` sets only the group and setgid, so the umask decides the mode. The `paper/` clone is not passed through `set_group`.
- Hooks embed the project's absolute path, so moving a project breaks them; rerun `scaffold.py install-hooks` there.
- A `"` in the git user name is not escaped in `DESCRIPTION`.

## Numbers builder (`numbers_build.py`, `numbers_emit.R`/`.py`)

- Only `%` is escaped in values: `_ # & $` in string values are not, and a `|` in a value breaks the ledger table row.
- If the ledger's rename fails, `numbers.tex` is restored. Only if that restore also fails is `numbers.tex` left ahead of the ledger, and the error says so. This is very unlikely.

## SessionStart hook (`session_start.py`)

- With more than about three ERROR lines at once, later priority lines go to `state/.hook.log`. The injected text says how many were moved there.
- Session start gives its git checks 20 seconds in all (`git_budget_seconds` in `limits.yml`). In a very large untracked tree, the status lines that didn't finish in time are reported as skipped, and the rules and current state still load.
- The working-tree numbers check walks its globs in Python, outside the git budget; a broad glob such as `**/*.tex` over a large data folder could still slow session start.
- A git process stopped at the deadline is killed, but its own child processes (submodule checks, fsmonitor hooks) may keep running in the background.
- Non-ASCII paths appear octal-escaped (`core.quotepath`).
- `state/.hook.log` grows between checkpoints. `/kit:checkpoint full` trims it to its last 500 lines.
- `state/.sessions/` keeps one small start record per conversation and is never pruned.

## Languages and environments (`scaffold.py`, `numbers_build.py`)

- `add-package` on a project that already has the language: if it fails after installing, the package stays in the ignored `renv/library/` or `.venv/` (harmless; nothing references it).
- `add-language`/`add-package`: an edit to one of the command's own files (`research.yml`, `CLAUDE.md`, `.gitignore`, `pyproject.toml`, `uv.lock`, `renv.lock`) made while it runs is overwritten if it fails, or included in its commit if it succeeds. Edits to any other tracked file are detected and left alone.
- `languages:` and `packages:` must each be on one line in `research.yml` (flow style); a block-style `research.yml` makes the `add-` commands refuse.
- renv's cache links packages into `~/.cache/R/renv` (mode 700), so other users can't load a project's R packages.
- renv's snapshot refuses user-library packages of unknown source (built with `R CMD INSTALL`, no Repository/Remote fields), such as a package installed from a local checkout; a project using one fails setup until it is installed from a repository or a remote.
- Python package templates pin `uv_build>=0.9.25,<0.10.0`; uv builds those offline only while it is 0.9.x, and after a uv upgrade the first editable rebuild fetches uv_build (network).
- A newline in a string value breaks its ledger row, as `|` does.
- `numbers_build.py` doesn't require the `make_numbers` script itself to be committed (that would block the edit-then-build loop); the ledger's Script column names it.

## Code review (`codex_review.py`)

- Vendored code in the repo (such as an analyst's code drop) counts toward the changed-code-file count and the status line.
- The /tmp and $TMPDIR exclusions use Codex settings that its help text does not document. Confirmed on codex-cli 0.163.0 (2026-11-11): the log header reads `sandbox: workspace-write [workdir]`, and a script run in a review was blocked from writing to `/tmp`, the copy's parent folder, the project and `$HOME`, while writes in the copy and its `.tmp` worked. `codex_review.py` reads the `sandbox:` line Codex prints first and stops Codex at once (exit 5) unless it reads `sandbox: workspace-write [workdir]`, so a Codex upgrade that changes it, even only its wording, stops reviews until it is rechecked. `codex sandbox -P :workspace` ignores these settings, so it can't be used for the check.
- A review snapshot of uncommitted work is a commit under `refs/kit-reviews/`; `git for-each-ref refs/kit-reviews/` lists them. Only refs of folders in the current reviews folder are pruned. A deleted review folder's ref stays, with its snapshot and any large untracked file in it, until removed with `git update-ref -d`.
- Housekeeping treats any registered worktree at `…/kit-review-*/copy` as a kit copy. Once its run looks dead, it is removed with `git worktree remove -f -f`, files included.
- Under a temp root other than the current one, a dead run's `kit-review-*` folder can keep its `pid` file after its copy is unregistered.
- A changed file whose name isn't valid UTF-8 makes the review status line an ERROR (at session start and in `/kit:checkpoint`) until the file is renamed.
- `finished` in `meta.json` is local time without a UTC offset. "Newest" can misorder reviews written on two machines in different time zones, or across a daylight-saving change.

## Code gate (`lint_code.py`)

### Not caught (accepted; the skill and `/kit:review` cover them)

- **Values that aren't numbers, dates or paths,** such as a clustering variable or a kernel name: no check can tell them from column names.
- **Paths built from pieces** (`file.path("data", "clean")`), **years typed as strings** (`"2019"`), and dates written in words.
- **Functions defined in unusual ways:** R `assign()`, `<<-`, `local(function(...))`, or `function` on the line after `<-`; Python `def` inside a top-level `if`, `try` or `with`. The skill says never to use these to get past the check.
- **A squash merge** has no `MERGE_HEAD`, so every line it brings counts as added.
- **A merge that commits on its own** (`git merge` without conflicts) runs git's `pre-merge-commit` hook, not `pre-commit`, and the kit installs only `pre-commit`; so no kit check sees it, in the code repo or the paper clone. A merge that stops (conflicts, `--no-commit`) is checked when it is committed.
- **Archived R code outside the four archive folder names.** `docs/` and `notes/` count as archived code for the other rules, but the `.renvignore` rule covers only `archive/`, `_archive/`, `legacy/` and `retired/`: a `.renvignore` in `docs/` would turn off `.gitignore` there, since renv reads one or the other in each folder. Archived R code no commit touches is not checked either; `lint_code.py --all` lists its folders.
- **Archived R the `.renvignore` check doesn't see:** R-kernel notebooks (`.ipynb`) and extensionless scripts with an R shebang, which renv reads; and a symlinked archive folder, whose files git doesn't track. A `.renvignore` whose later `!` lines or profile sections bring files back in is still accepted. An archive folder holding only files renv reads by name (`.Rproj`, `_quarto.yml`, `_bookdown.yml`, `_pkgdown.yml`, `.lintr`, `renv.lock`) isn't flagged; and R code under folders renv skips anyway (`packrat/`, `revdep/`, `vendor/`) is flagged for nothing.

### Blocked although legitimate (end the line with `# literal: <reason>`, or move the code)

- **Strings with a slash and no spaces** count as paths, so a label like `"Black/White"` is flagged. A URL is flagged on purpose: it is a data location.
- **Command-line functions** (click or typer commands) in a pipeline script are blocked; they belong in the library, with the script calling them.
- **An archive folder that a parent `.renvignore` already leaves out** still needs its own `.renvignore`: the check reads only the archive folder's file.
- **A script moved with heavy edits** (under git's 50% rename similarity) counts as leaving for the archive check, as it counts as new for the other rules: move it first, then edit it.
- **Merges and the archive check:** a merge that stops (conflicts, `--no-commit`) is checked against HEAD only, so merging a branch that adds a reader into a branch that archived the writer isn't caught; merging the other way is.
- **A script blocked from leaving by a wrong match:** the text check can think the pipeline reads a file only the leaving script writes when a basename is shared by two folders, or when the pipeline's real writer names the file in a way the check can't see. There is no comment escape: keep the script, or stop and ask.
- **A file moved with heavy edits** (under git's 50% similarity) counts as new, so its old functions and typed values are flagged too.

### Behaviour notes

- The run-all exemption applies to any file named `run_all.R` or `run_all.py`, wherever it is.
- In R, a one-element list parameter can't be told from a single string, so `param_path()` accepts `['a.csv']` in R and refuses it in Python.
- The readers find their files from their own place. In R that is the innermost `source()` that loaded `params.R`, or else the project folder above the working directory.

## Code map (`code_map.py`)

- Caller counts, parameter users and paper-output writers are found by text, not by running code. A name built at run time is missed.
- Repeats are blocks of six or more lines after spacing and comments are dropped. A copy with a renamed variable doesn't count as a repeat.
- A direct read of library data is reported only for data that a library loader reads, through `param()` or as an argument.
- **What the pipeline runs and makes** is found by text. Missed or wrong when: a file name is built at run time beyond the template forms (`%s`, `{x}`); a variable holds a path through more than one step, or across files; a project names files through its own configuration reader, so a pipeline script seems to write nothing (a parameter named in a string, and a name passed to any call, count as writes for the pipeline's own scripts, which keeps wrong findings down); a basename is shared by two folders (`es.csv` matches `a/es.csv` and `b/es.csv`); a reader or writer the lists don't name; a script run in a way the following rules don't see (a Makefile's pattern rules, a loop over `list.files()`, a bare name under four characters, a name with spaces). Also missed: names joined at run time (`paste0(dir, "/es.csv")`, `OUT + "/es.csv"`), tuple assignments, loops over a literal list of paths, and statements after a triple-quoted string with an unbalanced `(` (up to 30 lines).
- **The paper's tables and figures** count as used only when a `.tex` file of the manuscript names their stem; they take no part in the commit block.
- **A pipeline script whose name ends in `_test.py`** (`run_x_test.py`) is classed as a test, pytest's convention, so the code gate's rules skip it. The pipeline check still counts it as a writer.

## Near copies (`near_copy.py`)

The gate blocks a new library function that is 95% or more alike another library function (both at least 10 tokens), or 90% or more (both at least 30 tokens, about three lines), once local names and typed values are set aside. The map lists pairs from 80% (30 tokens or more) for review. The levels were measured on two projects' code: every sampled pair at the blocking levels was a copy to merge, and about three in four of the larger pairs from 80% to 90% were.

### Not caught (accepted; the skill and `/kit:review` cover them)

- **The same idea written differently,** such as a negative-zero rule written two ways, or terciles cut with two different functions.
- **Copies inside larger functions:** a copied block within a longer function lowers the whole function's similarity. The map's six-line repeats catch identical blocks.
- **Small functions below the levels,** such as `avg3(a, b, c)` beside `avg4(a, b, c, d)` (about 90% alike at 15 tokens). The number rule flags their typed 3 and 4, and review sees the rest.
- **Old functions:** pairs that are both already in the library, and an existing library function being edited, aren't blocked; `lint_code.py --all` counts them, as one finding for each function with an earlier near copy (three alike are two findings). A library function moved to another library file, or renamed with no other edit, stays old. A whole script moved into the library with few edits keeps its functions as old.
- **Functions too long or too deep to compare:** over 2,000 tokens (about 200 lines), or Python nested too deeply for the syntax-tree walk (hundreds of `elif` branches). The comparison's cost grows faster than the length.
- **Python columns** count only as direct string subscripts (`d["income"]`); `d.loc[:, "income"]` and lists of columns are strings.
- **Functions defined in unusual ways** (the same cases as the function rule above).

### Blocked although legitimate (end the definition line with `# distinct: <reason>`)

- **Deliberate variants with the same shape,** such as the head and tail of a list, or a mean and a median computed the same way, can reach the levels when they are small.
- **Thin wrappers that fix one argument,** such as two one-line formatters that call `fmt()` with a different suffix, are 100% alike. Calling `fmt()` with the argument is the kit's preference; mark the wrapper when its name carries meaning.
- **R S3 methods and Python overrides** with the same body shape.
- **A function renamed and edited in one commit** counts as new, so if its old version nearly copied another function, it is blocked now.

### Behaviour notes

- **A library file moved with heavy edits** into a file git doesn't pair with it: its functions keep their names, so they stay old for this check, but its lines count as new for the typed-value rule (fixed with parameters or `# literal:`).

- Of two new near copies in one commit, only the later one (by file and line) is checked, so `# distinct:` goes on that one.
- Drivers' `main` and `parse_args` are left out of every comparison.
- A function leaving a file that the same commit drops from research.yml's `library` key counts as moved, because the library before the commit is read with the key as it was then.

## Table checks (`lint_tables.py`)

### Not caught (accepted; review covers them)

- **Legend wordings the check doesn't recognise.** It reads `<symbol> p < <threshold>` (with `$^{*}$`, `\sym{*}`, `\textsuperscript{*}`, `\dagger`, `p-value`, parentheses and percents), "`***` Significant at the 1 percent level", "Significance levels: `*` 10%", fixest's `***: 0.01`, and lists such as "`***`, `**`, `*` denote significance at the 1, 5 and 10 percent levels". Any other wording reads as no legend, so its stars are reported; end the table with `%legend-ok: <reason>`.
- **Only `tabular`, `tabular*`, `tabularx` and `longtable` are read.** `tblr` (tabularray), `tabulary`, `NiceTabular`, `xltabular` and `tabu` are not, and neither are tables built by `\pgfplotstabletypeset` or other commands.
- **Tables reached through a macro** (`\newcommand{\tabinput}[1]{\input{tables/#1}}`) get the cell checks as files the manuscript never inputs, without the legend checks, if they are directly in `tables/`; files elsewhere reached this way, and files in subfolders of `tables/`, aren't checked.
- **An `S` column hidden more than one `\newcolumntype` deep** counts as a text column, so its numbers can be reported as hyphens.
- **Numbers outside cells** (captions, notes) are left to review.

### Blocked although legitimate (end the line with `%table-ok: <reason>`)

- **A cell whose text is a hyphen and digits on purpose,** such as a missing-value code `\texttt{-99}` in a codebook, or an event time `-1` printed in text (`$-1$` is the usual fix).
- **A macro in a generated file whose value is a negative number** counts even if the paper never uses it, or uses it only in math, where it prints correctly. Fix the writer (`\ensuremath{-}`), or end the line with `%table-ok`.

### Behaviour notes

- **`numbers.tex` writes negatives as `\ensuremath{-}1.2`** (0.5.0), and a value that rounds to zero without its sign (`-0.00` becomes `0.00`), so an interval bound's macro needs enough decimals in its format. A negative number macro inside `\num{}`, `\SI{}`, arithmetic (`\pgfmathparse`, `\fpeval`) or an `S`/`D` cell would break; none was found in five projects.
- **One finding per cell:** a cell with two hyphen minus signs (`[-0.5, -0.1]`) is one finding, which names the first.
- **An unresolved input** (one inside a table or figure float, a `longtable` or a `threeparttable`, or one naming a file in `tables/` or `generated/`) holds the baseline while no root of the manuscript resolves it, and the warning names it. Inputs inside `\iffalse … \fi` and `comment` environments are ignored, as are inputs whose name holds a macro parameter (`#1`).
- **A file the number lint's scanner can't parse** (such as `$$-$0.003$` in a cell) is skipped with a warning, and the baseline isn't lowered while it is.
- **An input that is a document of its own** (`subfiles`, `standalone`) is read for its body only.
- **`--report` counts table captions only**, not figure captions.
- **Committing from a worktree of the paper clone:** git points the hook at the worktree's index and HEAD, so the worktree's staged files and baseline are checked. A new or lowered baseline is written to the main clone's file and staged from there, so the worktree's `.lint_baseline_tables` shows as modified (and the main clone's file may change). The numbers check does the same.
- **A commit of named paths** (`git commit <paths>`) leaves a baseline the hook set or lowered out of the real index; `/kit:numbers` says how to stage it. This was already true of the numbers check's `.lint_baseline`.
- **Session start doesn't report table counts.** A table edited on Overleaf first shows up as a blocked local commit.
