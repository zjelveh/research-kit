---
name: review
description: Use when about to report a change to 2+ code files or a finished plan task as done in a research-kit project, or when the user asks for an independent review; Codex reviews the change and Claude checks every finding.
---

# Independent review

Codex, a different model, reviews the change; you then check every finding against the code and the user
approves the fixes.

## 1. Write the author's brief

Write a short file in your scratch folder with three parts:
- **Claims:** what the change is meant to do or show. Each numeric claim names its source file or table row.
- **Weak spots:** where you expect your own mistakes.
- **Outside the commits:** paths of scratch scripts and results that support a claim (they are reviewed too).

## 2. Run the review

Run it in the background, then tell the user it is running and may take up to 45 minutes:

    "${CLAUDE_PLUGIN_ROOT}/bin/kit" codex_review.py --project "${CLAUDE_PROJECT_DIR}" --brief <your brief> [--plan <plan file>]

Until it finishes, change none of the files under review. Exit codes: 0 complete, or nothing to review
(then no folder is made and you are done); 2 a usage or project error; 3 Codex missing or not signed in;
4 timeout or interrupt; 5 Codex failed or answered off-schema. The review folder is printed:
`notes/reviews/<YYYY-MM-DDTHHMM>-codex-<head>/`.

## 3. Check each finding

Open `report.md` and `findings.json`. For every finding, read the cited lines and, where cheap, reproduce
it with the command or test Codex gave. Write `verdicts.md` in the review folder, one entry per finding:
- **Confirmed**: what you checked.
- **Disputed**: only with evidence (a line, a test output, a plan or decisions passage). "Looks fine" is
  not evidence.
- **Unclear**: the question for the user.

## 4. Report

Briefly: confirmed findings with the fix you propose for each, disputed findings with their evidence, and
the open questions. One approval covers the batch; the user may strike items.

## 5. Fix

For each approved fix: a test that reproduces the problem, then the fix, then the project's tests; commit.
Then record each outcome in `verdicts.md` (fixed in commit X, or declined) and commit the review folder
in a second commit. A review's own fixes are not a new set point: the next review covers them.

## Codex unavailable (exit 3)

Ask the user whether to run a Claude-only review. If yes, give a fresh subagent the `brief.md` the script
wrote, with this note: it works in the real project, not a throwaway copy, so it must write nothing there
(its own scripts go in its scratch folder), and it reads the reviewed state with
`git show <REVIEWED>:<path>`. Then create `notes/reviews/<YYYY-MM-DDTHHMM>-claude-<head>/` with `brief.md`, its `report.md`, your
`verdicts.md` and a `meta.json` with `"reviewer": "claude"` and `"status": "complete"`. Mark it "not
independent" in the report. It does not clear the review status line.

## Done when
- [ ] The review folder has `report.md`, `findings.json` (not in a Claude-only review), `meta.json` and your `verdicts.md`.
- [ ] Every finding is confirmed, disputed with evidence, or put to the user as a question.
- [ ] Approved fixes are in, each with a test, and the project's tests pass.
- [ ] `verdicts.md` records each outcome, and the review folder is committed.

## Stop and ask
- The script exits 2, 3, 4 or 5 (for 4, ask whether to rerun with a longer `--timeout`).
- A finding would change a result, a number in the paper, or a decision in `state/DECISIONS.md`.
- You would dispute a finding without evidence.
