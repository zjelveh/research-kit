---
name: slides
description: Use when creating or revising a Beamer talk or slide deck in a research-kit project.
---

# Talks and slide decks

Every slide follows [style.md](style.md) and the house conventions in effect (`"${CLAUDE_PLUGIN_ROOT}/bin/kit" which slides-style`). Read both before drafting any slide; the conventions' word rules are those of the base voice (`"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-voice`).

## Layout

Each talk lives in `${CLAUDE_PROJECT_DIR}/slides/<talk>/`:
- `outline.md`: the locked outline;
- `script.md`: what the speaker says, one section per slide, in slide order;
- `talk.tex`: created by `scaffold.py new-talk` (phase 3) from the kit template `${CLAUDE_PLUGIN_ROOT}/templates/beamer/talk.tex`. Never copy the template by hand: its paths are placeholders.

`talk.tex` reaches the paper through relative paths that `scaffold.py new-talk` writes from `.claude/research.yml`: the `numbers_tex` and `notation_tex` files, and the paper's `figures/` and `tables/` folders, which sit beside the `generated/` folder that holds `numbers.tex` (`paper/draft/figures/` when `numbers_tex` is `paper/draft/generated/numbers.tex`). Use those figures by file name only, `\includegraphics{<file>}` (`\graphicspath` finds them), and those tables as `\input{\papertables/<file>}`. A table or figure the manuscript keeps in another folder (such as `paper/Tables/`) is reached the way the manuscript reaches it, by a relative path from the talk folder (`\input{../../paper/Tables/table1}`). Never edit the generated paths by hand, and never copy numbers, tables or figures into the talk folder.

## Phases

### 1. Gather input
Ask for the talk's length, the audience and venue, the paper sections or notes it draws on, and the one message the audience should leave with. Agree on the `<talk>` folder name (letters, digits, `.`, `_` and `-`, starting with a letter or digit; no spaces); for a new talk, stop if `slides/<talk>/` already exists. If `paper/` isn't attached, stop and ask.

### 2. Outline
Draft `outline.md`: one line per slide (frame title and what the slide shows), grouped by section, with a slide count that fits the length (about one slide per minute). Show it in full and revise until the user approves. Then mark it `Locked YYYY-MM-DD` at the top. No slide is drafted before the lock.

### 3. Set up
Create `slides/<talk>/talk.tex` from the template:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py new-talk <talk> --project "${CLAUDE_PROJECT_DIR}"
```
It stops (exit 2) if `talk.tex` already exists, `paper/` isn't attached, the talk name is invalid, or a path to the paper contains a LaTeX special character. Then set `\title` and `\author`, and create `script.md` with one heading per outline slide.

### 4. Build slide by slide
For each slide, in outline order:
1. Draft the frame in `talk.tex` and its section in `script.md`.
2. Check the frame against `style.md` and the house conventions, then show both in full and wait for approval. Never batch slides.
3. Apply the approved text exactly.

If a slide needs a number that has no macro, add it through `/kit:numbers` first. If it needs a symbol that isn't in `notes/notation.md`, stop and ask.

### 5. Compile, check, commit
1. Regenerate the inputs:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" notation_tex.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   Run `numbers_build.py` (see `/kit:numbers`) if `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`) doesn't exist yet, or if any number is stale: a macro's `commit=` tag differs from the latest commit of its `src=` file (`git log -1 --format=%H -- <src>`).
2. Build in `slides/<talk>/` with `latexmk -pdf -interaction=nonstopmode talk.tex`. Never use `-draftmode`. If the build fails, stop and report.
3. Show the user the PDF.
4. Run the slides numbers check:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" lint_numbers.py --project "${CLAUDE_PROJECT_DIR}" --gate slides -v
   ```
   Exit 1: each finding becomes a macro, or, if it is not a result, gets `%num-ok` with approval. Exit 2: stop and ask.
5. Commit in the code repo, staging only `outline.md`, `script.md` and `talk.tex`. The pre-commit hook runs the same numbers check.

## Revising an existing talk

Read `outline.md`, `script.md` and `talk.tex` first. Adding, removing or reordering slides goes back through phase 2 (update and re-lock the outline); a change within a slide goes through phase 4. Finish with phase 5.

## Done when
- [ ] `outline.md` is locked with the user's approval.
- [ ] Every slide and its `script.md` section were approved one at a time.
- [ ] `latexmk -pdf` builds without errors, and the user has seen the PDF.
- [ ] `lint_numbers.py --gate slides` exits 0.
- [ ] `outline.md`, `script.md` and `talk.tex` are committed.

## Stop and ask
- `paper/` is not attached; or, for a new talk, `slides/<talk>/` exists in phase 1 or `slides/<talk>/talk.tex` exists in phase 3.
- A slide needs a symbol with no `notation.md` entry.
- `notation_tex.py`, `numbers_build.py`, `lint_numbers.py` or `scaffold.py new-talk` exits 2.
- `latexmk` fails.
- The user wants to add, remove or reorder slides after the outline is locked (go back to phase 2).
