---
name: writing
description: Use when drafting, editing or line-editing any manuscript prose (paper sections, abstract, captions, response letters) in a research-kit project.
---

# Manuscript prose

Work from the argument down: settle the paper's argument, outline a section, draft the whole section, and do sentence work last. Read this whole file first, then load the voice and the patterns (section 1) and the venue file (section 3).

Rules marked **(hard rule)** are never set aside. The others filter good prose; they don't replace it. If applying an ordinary rule makes a sentence worse, the prose wins: write the better sentence and name the rule you set aside. If a hard rule seems to make a sentence worse, stop and ask. Never fix stilted prose by adding prohibitions: look at the structure and the patterns first.

## 1. Voice and patterns

Each is its own file, so each user can set their own. Find the ones in effect and read both in full:
```
"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-voice
"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-patterns
```
The voice says how sentences sound. Its rules apply to all prose, captions and slide text, and its **(hard rule)** marks are hard rules as defined above. The patterns say how paragraphs and sections are built; they guide outlines and section drafts.

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
2. Read the venue file in effect, `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which venue <venue>`, and apply it on top of the voice and the patterns.
3. If `research.yml` is missing or has no `venue` key, or `kit which venue` exits 2: **stop and ask**. Never continue without a venue.
4. If a venue rule contradicts a voice rule: stop and ask. A venue's required structure (mandated sections, their order) wins over a section pattern, and the outline notes it.

The kit ships the venue `undecided`; `"${CLAUDE_PLUGIN_ROOT}/bin/kit" customize venue <name>` starts a new one in the personal folder.

## 4. Which level of work

| Job | Levels |
|---|---|
| A new section, or a section rewritten | 5.1 argument, 5.2 outline, 5.3 section draft, then 5.4 for touches |
| A change to approved prose: wording, a number, a citation | 5.4 |
| A caption, a table or figure note, a response letter, a one-line fix | 5.4 |

## 5. The levels

Before any level, pull from Overleaf: `git -C "${CLAUDE_PROJECT_DIR}/paper" pull`. If it fails or conflicts, stop and ask. Then read `notes/argument.md` if it exists: the voice's magnitude rule finds a claim's home there.

### 5.1 Argument: `notes/argument.md`
Read it in full. It holds the argument in four to eight sentences, each section's job and claims (with IDs C1, C2, …), and the redundancy map, which gives each repeated claim, number or definition one home.
- If it is missing, or still the template (its `Approved:` line reads `(not yet)`), offer to write it with the user from the kit's template (`${CLAUDE_PLUGIN_ROOT}/templates/project/notes/argument.md`), using the section patterns. Show it in full and wait for approval. Then set that line to `Approved: YYYY-MM-DD` and commit it in the code repo.
- If the user declines, only line edits (5.4) are available. Say so.
- A change to the argument file, including a claim's home, is shown as a before/after and approved before section work depends on it; then update the `Approved:` date.

### 5.2 Section outline: `notes/outlines/<section>.md`
`<section>` is the section's slug: lowercase letters, digits and hyphens, such as `results` or `data-and-approach`.
1. Write one sentence per paragraph, each naming the paragraph's job in the pattern and listing the claim IDs it uses. Read in order, the sentences argue the section's point. Note any departure from the section pattern, and why.
2. Show it in full and wait for approval. Then mark it `Approved: YYYY-MM-DD` at the top and commit it in the code repo.
3. A changed outline is approved again before the draft changes.

### 5.3 Section draft
1. The paper repo must have no uncommitted changes in the files the section touches. Otherwise stop and ask.
2. Draft the section in one pass from the approved outline, with the neighbouring sections open. Draft a long section a subsection at a time.
3. Write the draft into the paper's working tree only to build it (5.6), and read the section in the PDF with its neighbours.
4. Reverse outline: list the paragraphs' first sentences in order. If they don't argue the section's point, fix the structure before the wording.
5. Section sweep: within the section, each claim, number and definition appears once, either in its home or as a back-reference or planned recap listed in the redundancy map.
6. Run the pre-send checks for a section (section 8).
7. Show the user the section (the PDF pages and the source), the reverse outline, and any departures from the outline. **The user approves the section as a unit.**
8. If the user asks for changes, revise and repeat steps 3–7; if the change alters the outline, approve the outline again first (5.2).
9. If the user rejects the draft, restore the touched files from the paper repo's HEAD (`git -C "${CLAUDE_PROJECT_DIR}/paper" restore <files>`) and delete any new files the draft added; nothing was committed.
10. On approval: the boundary sweep and the knock-on sweep (section 6). Items the user takes up are made in the section and shown with it, so they are committed together. Then commit in the paper repo and push to Overleaf with approval.

### 5.4 Line edits
1. Show the exact block: file, line range and the current text.
2. Show the full before and after within its paragraph, with a short analysis of the problem and the options where there is a real choice. Wait for approval. Show several line edits together only when the user asks for a batch.
3. Apply the approved text exactly, and run the knock-on sweep (section 6) after each. If a line edit adds, drops or reorders paragraphs of an outlined section, update the outline to match and show that change too.
4. Build (5.6), then commit in the paper repo and push to Overleaf with approval. If the numbers or table check blocks the commit, see `/kit:numbers`.

### 5.5 Paper sweep
At two milestones: once the core sections are drafted, before the introduction, discussion and abstract are written; and before submission. List, by section, where each claim ID, results macro, key term and citation appears. Each repeat is kept as a planned recap (listed in the redundancy map), cut, or turned into a back-reference. Update the map when a claim's home moves. Report the list; each change goes through 5.4.

### 5.6 Build
Build each main file from its own folder: `latexmk -pdf -cd <main file>`. A main file is a `.tex` with `\documentclass` among the files that `lint.paper.globs` in `.claude/research.yml` match; it may sit in a subfolder of `paper/`, such as `paper/draft/`. If one main file names another in `\externaldocument`, build that one first. Never use `-draftmode` for a PDF anyone will see. If the build fails, stop and report; don't commit.

## 6. Sweeps after a change
- **Knock-on sweep** (after each approved line edit, and when a section is approved). Change nothing during the sweep; report a list (file, line, reason), and each item the user takes up goes back through 5.4.
  - Read the rest of the paper, and the slides and notes where relevant, for passages the change affects: ones that restate or summarize it (abstract, introduction, conclusion), depend on it, refer to it, or now contradict it in substance, terms, notation or strength of claim.
  - Check retired wording mechanically. Pass each phrase the change retired (a renamed term, a dropped framing, a changed claim):
    ```
    "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_stale.py --project "${CLAUDE_PROJECT_DIR}" "<old phrase>" ...
    ```
    Exit 1 lists where the old wording remains; add those hits to the list. Exit 2: stop and ask.
  - Before committing, sweep once more across all changes since the last commit: several changes together can affect passages that none of them affects alone.
- **Boundary sweep** (when a section is approved): reread the end of the section before and the start of the one after. No restated setup, and no point made on both sides of the break.

## 7. Numbers
- A result in prose is always a macro from `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`), including integers in math (`$N = \nObs$`), which the lint can't see. See `/kit:numbers`.
- If the macro doesn't exist, add it through `/kit:numbers` first, then write the sentence.
- Never hand-edit the paper's `generated/` folder. Change the source (a `make_numbers` script in `analysis/numbers/`, or `notes/notation.md`) and regenerate.
- The pre-commit numbers check blocks a commit that adds a bare number.

## 8. Pre-send checks
Run before showing anything, at its level.

**Every level**
- [ ] Venue file read and applied?

**Outline and section**
- [ ] The checks under the patterns file's `### Pre-send checks` heading pass? If it has no such heading, check each of its patterns.

**Section and line edit**
- [ ] The checks under the voice file's `### Pre-send checks` heading pass? If it has no such heading, check each of its rules.
- [ ] Every assumption referred to by its name; every formal result followed by an intuition paragraph; every symbol typeset through a `notation.md` macro?

**Outline**
- [ ] One sentence per paragraph, each naming its job and its claim IDs? In order, do they argue the section's point?
- [ ] Departures from the section pattern noted, with the reason?

**Section**
- [ ] Reverse outline done, and it argues the point? Section sweep done?

**Line edit**
- [ ] Shown as a full before/after within its paragraph?

## Done when
- [ ] For section work, the argument file is approved (its `Approved:` line has a date). Line edits need no argument file.
- [ ] Each outline, section and line edit was approved as shown and applied exactly.
- [ ] Each sweep was reported, and each item handled or explicitly deferred by the user.
- [ ] `latexmk -pdf` builds without errors.
- [ ] The prose is committed in the paper repo and, with the user's approval, pushed to Overleaf; the argument file and outlines are committed in the code repo.

## Stop and ask
- `research.yml` is missing, has no `venue` key, or the venue file doesn't exist.
- A venue rule contradicts a voice rule.
- `git pull` fails or conflicts.
- The paper repo has uncommitted changes in files a section draft would touch.
- An outline or a draft would contradict the argument file.
- A hard rule seems to make a sentence worse.
- A result has no macro, or a symbol has no `notation.md` entry.
- A citation hasn't been verified against a retrieved source (use `/kit:lit`).
- `check_stale.py` exits 2, `latexmk` fails, or the numbers or table check blocks a commit.
