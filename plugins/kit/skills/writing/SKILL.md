---
name: writing
description: Use when drafting, editing or line-editing any manuscript prose (paper sections, abstract, captions, response letters) in a research-kit project.
---

# Manuscript prose

Read this whole file before drafting or editing prose, then load the base voice (section 1) and the venue file (section 3). Run every paragraph through the pre-send checklist (section 6) before showing it.

Rules marked **(hard rule)** are never set aside. The others filter good prose; they don't replace it. If applying an ordinary rule makes a sentence worse, the prose wins: write the better sentence and name the rule you set aside. If a hard rule seems to make a sentence worse, stop and ask.

## 1. Base voice

The base voice is its own file, so each user can set their own. Find the one in effect and read it in full:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-voice
```
Its rules apply to all prose, captions and slide text; its **(hard rule)** marks are hard rules as defined above.

## 2. Methods-paper rules
- Every assumption has a name (for example, "Assumption 2 (Exchangeability)"), and later text refers to it by that name, never as "the assumption above".
- Each formal result (theorem, proposition, lemma, corollary) is followed by a paragraph of intuition.
- Symbols come only from `notes/notation.md`, typeset through the macros in `notation.tex` (the `notation_tex` path in `.claude/research.yml`). A new symbol is added to `notation.md` first, with approval. After any `notation.md` edit, run:
  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/kit" notation_tex.py --project "${CLAUDE_PROJECT_DIR}"
  ```

## 3. Venue slot
At the start of every writing task:
1. Read `venue` from `${CLAUDE_PROJECT_DIR}/.claude/research.yml`.
2. Read the venue file in effect, `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which venue <venue>`, and apply it on top of the base voice.
3. If `research.yml` is missing or has no `venue` key, or `kit which venue` exits 2: **stop and ask**. Never continue with the base rules alone.
4. If a venue rule contradicts a base rule: stop and ask.

The kit ships the venue `undecided`; `"${CLAUDE_PLUGIN_ROOT}/bin/kit" customize venue <name>` starts a new one in the personal folder.

## 4. Editing process
1. Pull from Overleaf: `git -C "${CLAUDE_PROJECT_DIR}/paper" pull`. If it fails or conflicts, stop and ask.
2. Show the exact block to change: file, line range and the current text.
3. One paragraph at a time: show the full before and after, with a short analysis of the problem and the options where there is a real choice. Wait for approval. Never batch paragraphs.
4. Apply the approved text exactly.
5. Sweep for knock-on changes after each edit. Change nothing during the sweep; report it as a list (file, line, reason), and each item the user takes up goes back through steps 2–4.
   - Read the rest of the paper, and the slides and notes where relevant, for passages the edit affects: ones that restate or summarize it (abstract, introduction, conclusion), depend on it, refer to it, or now contradict it in substance, terms, notation or strength of claim.
   - Check retired wording mechanically. Pass each phrase the edit retired (a renamed term, a dropped framing, a changed claim):
     ```
     "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_stale.py --project "${CLAUDE_PROJECT_DIR}" "<old phrase>" ...
     ```
     Exit 1 lists where the old wording remains; add those hits to the list. Exit 2: stop and ask.
6. Build each main file from its own folder: `latexmk -pdf -cd <main file>`. A main file is a `.tex` with `\documentclass` among the files that `lint.paper.globs` in `.claude/research.yml` match; it may sit in a subfolder of `paper/`, such as `paper/draft/`. If one main file names another in `\externaldocument`, build that one first. Never use `-draftmode` for a PDF anyone will see. If the build fails, stop and report; don't commit.
7. Before committing, sweep once more across all edits since the last commit, the same way as step 5. Several edits together can affect passages that none of them affects alone.
8. Commit in the paper repo, then push to Overleaf with approval. If the numbers check blocks the commit, see `/kit:numbers`.

## 5. Numbers
- A result in prose is always a macro from `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`), including integers in math (`$N = \nObs$`), which the lint can't see. See `/kit:numbers`.
- If the macro doesn't exist, add it through `/kit:numbers` first, then write the sentence.
- Never hand-edit the paper's `generated/` folder. Change the source (a `make_numbers` script in `analysis/numbers/`, or `notes/notation.md`) and regenerate.
- The pre-commit numbers check blocks a commit that adds a bare number.

## 6. Pre-send checklist
Run on every paragraph before showing it.

**Voice**
- [ ] The checks under the voice file's `### Pre-send checks` heading pass? If it has no such heading, check each of its rules.

**Methods**
- [ ] Every assumption referred to by its name?
- [ ] Every formal result followed by an intuition paragraph?
- [ ] Every symbol typeset through a `notation.md` macro?

**Process**
- [ ] Venue file read and applied?
- [ ] One paragraph, shown as a full before/after?

## Done when
- [ ] Each changed paragraph was approved as shown and applied exactly.
- [ ] The pre-send checklist passes.
- [ ] Each sweep list (after every edit, and before the commit) was reported, and each item was handled or explicitly deferred by the user.
- [ ] `latexmk -pdf` builds without errors.
- [ ] The change is committed in the paper repo, and pushed to Overleaf unless the user declined.

## Stop and ask
- `research.yml` is missing, has no `venue` key, or the venue file doesn't exist.
- A venue rule contradicts a base rule.
- `git pull` fails or conflicts.
- A hard rule seems to make a sentence worse.
- A result has no macro, or a symbol has no `notation.md` entry.
- A citation hasn't been verified against a retrieved source (use `/kit:lit`).
- `check_stale.py` exits 2, `latexmk` fails, or the numbers check blocks a commit.
