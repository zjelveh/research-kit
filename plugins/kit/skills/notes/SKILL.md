---
name: notes
description: Use when recording a research idea, conjecture, memo or notation change in a research-kit project.
---

# Research notes

Three kinds of notes live in `${CLAUDE_PROJECT_DIR}/notes/`. Edits to existing text are prose edits: show the full before and after, and apply only with approval. The paper's argument (`notes/argument.md`) and the approved section outlines (`notes/outlines/`) are `/kit:writing`'s; change them there.

## Research questions: `notes/research_questions.md`

The paper's spine until a draft exists. One entry per research thread:

```markdown
## RQ<n>: <short name>
- **Question:** ...
- **Current conjecture:** ...
- **What would settle it:** ...
- **Status:** ...
- **Links:** memos, simulations and literature, as paths or citation keys
```

A new thread is added with approval, numbered after the highest existing `RQ`.

## Memos: `notes/memos/YYYY-MM-DD-slug.md`

One memo per piece of reasoning or evidence, with this header:

```markdown
# <Title>
- **Question:** the RQ it addresses
- **Claim:** one sentence
- **Status:** exploratory | supported | refuted
```

The body gives the reasoning or evidence, with paths to the code, outputs and literature it rests on.

- **Memos are never rewritten.** A later result gets a new memo that links back to the earlier one.
- **Promotion:** when a memo's conclusion bears on a thread, propose the change to that thread's entry in `research_questions.md` (conjecture, status, links) as a before/after, and apply it only with approval.

## Notation: `notes/notation.md`

A table with the header `| Symbol | Meaning | Macro | Introduced |`. Symbol and Macro cells are in backticks; a macro is a backslash plus letters only, and unique; no cell contains `|`.

1. Show the row to add or change, and apply it only with approval.
2. Before renaming or removing a macro, find where it is used, as a whole macro name and outside the two files that define it:
   ```
   grep -rnE '\\oldMacro([^A-Za-z]|$)' "${CLAUDE_PROJECT_DIR}/paper" "${CLAUDE_PROJECT_DIR}/slides" "${CLAUDE_PROJECT_DIR}/notes" --exclude-dir=generated --exclude=notation.md
   ```
   Exit 1 means unused. If it finds anything (exit 0), stop and ask.
3. After every edit to `notation.md`, regenerate `notation.tex` (the `notation_tex` path in `.claude/research.yml`):
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" notation_tex.py --project "${CLAUDE_PROJECT_DIR}"
   ```
4. `notation.tex` is in the paper repo. Commit it there, and push to Overleaf with approval, so the web copy compiles.

## Done when
- [ ] Every new or changed entry, memo header, promotion and notation row was approved as shown.
- [ ] No existing memo was rewritten.
- [ ] After a notation edit, `notation_tex.py` exited 0, and `notation.tex` was committed, and pushed unless the user declined.

## Stop and ask
- A macro to rename or remove is still used in the paper, slides or notes.
- `notation_tex.py` exits 2, or the usage grep exits 2.
- A memo's claim contradicts a thread's current conjecture and the user hasn't said which stands.
