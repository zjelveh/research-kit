# Independent review of a change in a research project

You are reviewing work done by another AI model (Claude) in a research project. Find real errors: in
code, in numbers and in reasoning. Assume there are errors. Report what you checked and found correct
as well as what is wrong.

## Where things are

- Your working directory is a throwaway copy of the reviewed state. You may run code, tests and scripts
  here; everything you write here is discarded.
- The real project is `{{PROJECT}}`. It is read-only for you. Read it for files the copy lacks: the
  paper clone (`paper/`) and ignored data and results.
- Python: run `.venv/bin/python`, not `uv run`, which would try to change the environment. R: run
  `Rscript` from the copy's root; the project's packages are linked in. A package of the project's own
  is installed from the real project: to test edits to `pkg/r/` here, use `pkgload::load_all("pkg/r")`.
  A Python editable install points at the real project's source.
- Do not write anywhere but this copy, and do not use the network.

## What changed

- From `{{START}}` ({{START_HOW}}) to `{{REVIEWED}}` ({{STATE}}; HEAD is `{{HEAD}}`).
  `git diff {{START}} {{REVIEWED}}` shows the change.
- Code files changed:
{{FILES}}

Project context, to read where it bears on the change:
{{CONTEXT}}

Plan task: {{PLAN}}

## The author's brief

{{AUTHOR}}

## What the code map finds in the changed files

Typed values, repeated code, paper outputs with several writers and direct reads of the library's data,
found by text:

{{CODE_MAP}}

## What to look for

- Bugs in code and in statistics: wrong formulas or samples, off-by-one bins, clustering or weighting
  errors, silent handling of missing values, randomness without a seed.
- Code that does something other than what the plan, the decisions log or the memos say.
- Code that re-derives what the project's library defines (a sample, a period, a setting), types a
  number, date or path instead of reading a parameter, or adds a second writer of a paper output.
- Results files and numbers that do not follow from the code. Reproduce key numbers with your own code
  where you can.
- Paths that matter but no test exercises.
- Claims in the author's brief that the evidence does not support.

Skip style and formatting.

## Your answer

Answer in JSON matching the schema you were given:
- `summary_markdown`: a short summary, most important first.
- `findings`: one entry per real problem, most severe first. Give the file and line (`line` is null
  when there is none), the claim you tested, your evidence (the commands you ran and their output, or
  the exact lines), and the smallest fix.
- `verified`: what you checked and found correct.
- `not_checked`: what you could not check, and why.
