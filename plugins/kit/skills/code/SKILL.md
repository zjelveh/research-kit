---
name: code
description: Use when writing or changing analysis code in a research-kit project, from a quick question about the data to a new analysis or a fix; plotting code also follows /kit:figures, and paper numbers follow /kit:numbers.
---

# Analysis code

The project's library is the paper's code as it will be released: every step that produces a result in the paper (data preparation, samples, estimation, the computations behind each number, the tables and the figures) is a library function. Pipeline scripts are thin drivers: they read parameters, call library functions in order, and write outputs. The parameter files hold every number, date and path the code uses.

A request calls the library. When a library function nearly fits, extend it; when the request is a genuine one-off, an explore script calls the library and adds only the one-off part; whatever comes to feed the paper moves into the library. Never rebuild in a script what the library does. Read this whole file first.

**(hard rule)** Code never types a number other than 0, 1, 2 or 100, a date, or a path or file name. Each goes in a parameter file, with a comment saying what it is and why, and code reads it with `param("name")`. A line that must keep a value ends with `# literal: <reason>`, which review sees.

**(hard rule)** A pipeline script defines no function (an entry point named `main` or `parse_args` aside): the paper's logic lives in the library, and the script calls it.

The kit's pre-commit check blocks a commit whose added lines break either rule. Tests and archived code are exempt from both. The second rule doesn't apply to the library, a package, explore scripts or the run-all script, and a function a script already had may still be edited. A file moved with heavy edits, so that git no longer sees it as moved, counts as new, functions included. A package keeps the first rule in its own form (section 4). "Function" includes a Python class or a named lambda; never rewrite a blocked function as a lambda, `local()` or `assign()` to get past the check: move it into the library.

## 1. Map first

Before writing any code, run the map and read it:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" code_map.py --project "${CLAUDE_PROJECT_DIR}"
```
It lists the library's functions, with how many files call each one, and the parameters, with their values and the scripts that use them. The library is what `library:` in `.claude/research.yml` names (folders or files), or else the project's package. Also read the packages the project already has, in `renv.lock` or `pyproject.toml`.

- **The summary says `library: none`:** stop and ask where shared code should live. It can be a package (`"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-package r|python`), or folders and files named in `library:`.
- **A warning that git ignores library code:** stop and ask. Code that git ignores is not under version control.
- **A warning about a parameter file's format:** fix it first (section 3).
- **A warning that a parameter file is not the kit's:** the project has its own file of that name. Stop and ask before renaming or converting it; other code may read it.
- **No `analysis/params.yml`** (a project made before the parameter files): run `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-params`. It writes the parameter files and readers the project lacks, ignores `analysis/explore/out/`, commits those files, and turns the code check on in the project's hook. It refuses, and changes nothing, when a file of the same name is the project's own. Run it again when `param_path()` is missing: a reader from an older kit version is refreshed.
- **The user asks for a clean-up of the project's code:** run the map with `--all`, and `lint_code.py --all` for the typed values by file, and work from those lists.

## 2. Where the code goes

- **A quick question** ("what share of cases had X, by year?"):
  - Write a new script, `analysis/explore/YYYY-MM-DD-<topic>.R` (or `.py`), that starts with three comment lines:
    ```
    # Question: <the question, as asked>
    # Date: YYYY-MM-DD
    # Commit: <short hash of the code repo's HEAD when it ran>
    ```
  - Its body calls library functions and adds only the one-off calculation. It prints its answer.
  - Its one-off values (a cutoff, a year) go in `analysis/explore/params.yml`, which needs no approval.
  - Files it writes go to `analysis/explore/out/`. Before writing there, run `git -C "${CLAUDE_PROJECT_DIR}" check-ignore -q analysis/explore/out/x`. If it exits 1, stop and ask to add `analysis/explore/out/` to `.gitignore`: outputs from the data can be large or sensitive.
  - Commit the script and the explore parameters in the code repo; never its outputs.
  - A result that will appear in the paper moves into the pipeline first, with its values moved into `analysis/params.yml`. An explore script is never the source of a paper number.
- **A change to the paper's pipeline:** change the library function that does that step, and its driver only where the call changes. A new step is a new library function, called from the driver of its stage. A new driver only for a new stage. Never save a copy (`_v2`, `_new`, `_fixed`), because git keeps the old version.
- **The run-all script:** one script (`analysis/run_all.R`, `run_all.py` or a Makefile) runs the drivers in order, so a replicator runs one command. A new driver goes into it. If the project has none, write one when the first driver is added, or stop and ask in a project that has many drivers already.
- **Retiring a script:** `git mv` it into an `archive/` folder, so it is out of the pipeline and the map no longer counts it. A note saying it is retired is not enough.

## 3. Parameters

- **Two files.** `analysis/params.yml` holds what the pipeline uses; `analysis/explore/params.yml` holds what quick questions use. A name lives in one file only, and pipeline code reads only the pipeline file.
- **The format** is a strict subset of YAML, which the project's readers parse without packages. One `name: value` per line, a lowercase name, and the comment line directly above saying what the value is and why:
  ```yaml
  # Smallest group the tables report; smaller groups are suppressed.
  min_group_size: 20
  # First and last year of the analysis panel.
  panel_years: [1990, 2019]
  # The cleaned analysis dataset, relative to the project root.
  analysis_data: 'data/analysis.parquet'
  ```
  Values are numbers, single-quoted strings (dates and paths always quoted), `true` or `false`, or a one-line list of numbers only or of strings only. No comment after a value: the comment goes on the line above. Paths are relative to the project root.
- **Reading them:** R: `source("analysis/params.R")` (by its path from the script's working folder), then `param("min_group_size")`. Python: put the project's `analysis/` folder on `sys.path`, `from params import param, param_path`, then `param("min_group_size")`. The readers find the parameter files from their own place, so a script may run from any folder in the project, and a missing `analysis/params.yml` is an error, as is an unknown name. Read a path with `param_path("analysis_data")`, which joins it to the project root, so it works from any folder; `param()` returns the path as written.
- **Changing a pipeline value** is shown as a before/after for approval, with the scripts the map lists as its users; then say which outputs are stale and rerun them. Adding a pipeline value is shown with the code that uses it.
- **Design settings are parameters too,** when they are strings the check can't see: the clustering variable, the kernel, an estimator option. Put them in the pipeline file and read them with `param()`.

## 4. The library

The library holds every step that produces a result in the paper, as functions:
- **Definitions:** loading, cleaning, sample restrictions, variable and outcome construction. Only the library reads the project's datasets. Scripts may read result files (a numbers source, a figure's data) through `param()`.
- **Analysis:** estimation, robustness checks, simulations, and the computation behind each number the paper reports.
- **Reported quantities:** how each is computed, such as a minimum detectable effect, a rejection rule or the significance stars.
- **Outputs:** the code that builds each table and each figure. A driver calls it with the results and the output path.

Functions that define data or compute a reported quantity get a test when they are written; the rest get one when they are changed.

Then:
- **One function per analysis sample.** Its settings are arguments. In a library folder they may default to `param()`: `paper_sample <- function(d, window = param("paper_window"))`. In a package they are plain arguments (`paper_sample <- function(d, window)`), and the calling script passes `paper_sample(d, window = param("paper_window"))`. A test pins its row count on a small fixture. Scripts narrow the sample further only in an explore script that says why.
- **One definition per concept.** Named variants (a long and a short window) sit beside the main one, as parameters or arguments. A function takes the population it is computed on as an argument, and never assumes one.
- **A one-off calculation** stays in its explore script. When it comes to feed the paper, or a second script needs it, it moves into the library with a test, and the scripts call it.
- **A function that nearly does the job** is extended, for example with an argument, rather than copied into a sibling.
- **Changing what a library function does:** find its callers (the map's `callers` count, then a search for `name(`), run their tests, and tell the user which outputs are now stale.
- **Two builders that must coexist,** such as a legacy panel kept for one output, get a test that they agree: keys, row counts and key columns.
- **Scripts never assign to library variables;** they pass arguments.
- **A package (`pkg/`)** can't read the project's parameter files, because it must work outside the paper. Its functions take values as arguments, which the calling scripts pass with `param()`; a number in package code is a named constant or a function default, never typed inline, and package code never calls `param()`. The check enforces both.
- **Tests** go where the project keeps them. If it has none, stop and ask.

## 5. Methods and settings

- Estimators, standard errors, the bootstrap, regression discontinuity and event-study designs, regression tables and plots use a package the project already has. If none does the job, propose a well-established one, then install it with renv or uv and commit the lockfile (`/kit:numbers`, "Packages the scripts need").
- Write a method by hand only when no package does the job, with a comment saying why.
- Pass every option that matters explicitly, from the parameters. Never leave a substantive choice to a package default: two calls that differ only in a default run different estimators.
- Each paper table or figure has one script that writes it. Results in prose are macros (`/kit:numbers`).

## 6. Before showing the code

Run the map on the files you changed or added:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" code_map.py --project "${CLAUDE_PROJECT_DIR}" --files <changed files>
```
It lists the typed values on the changed lines, repeats, paper outputs with several writers, and direct reads of the library's data. Fix each one the change introduced, or say why it stays. The map keeps no baseline, so judge what is new from the change's diff. The pre-commit check will block the typed values and the functions in pipeline scripts that the map listed.

**When a commit is blocked** with `code gate: N findings`, each line names a file and a line. For a typed value, with a hint when it is already a parameter: move it into the right parameter file, or end the line with `# literal: <reason>` when it can't be a parameter. For a function defined in a pipeline script: move it into the library and call it from the script; if the project has no library yet, stop and ask where it lives. A string that is only an extension (`".csv"`, `"*.csv"`) is not flagged, so a name built in code is fine. Never commit with `--no-verify`.

## Pre-send checks
- [ ] The map was read before writing, and every library function and parameter that fits is used?
- [ ] (hard rule) No typed number, date or path on a changed line, unless it ends in `# literal: <reason>`?
- [ ] (hard rule) No function defined in a pipeline script; the drivers only read parameters, call the library and write outputs?
- [ ] New values are in the right parameter file, each with its comment; a changed pipeline value was approved?
- [ ] A quick question is a dated explore script with its three header lines, and no script is a copy of another?
- [ ] Every step that feeds the paper is a library function; definitions and reported quantities have tests; each sample is one function; a new driver is in the run-all script?
- [ ] No method written by hand where a package does it, and no substantive option left to a default?
- [ ] The map's `--files` check shows nothing the change introduced, or each item is explained?

## Done when
- [ ] The pre-send checks pass.
- [ ] The library's tests pass, and so do the tests of the callers of any library function that changed.
- [ ] The code and the parameter files are committed in the code repo, and explore outputs are not.
- [ ] For a change to 2+ code files, `/kit:review` has run.

## Stop and ask
- The map's summary says `library: none`, or warns that git ignores library code.
- `analysis/explore/out/` isn't ignored by git, and the script needs to write a file.
- A pipeline parameter would change, or a library change would alter numbers already in the paper.
- The project has nowhere for tests.
- The map or the check exits 2.
