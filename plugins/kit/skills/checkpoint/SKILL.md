---
name: checkpoint
description: Use when ending a session, before a context compaction, or when the user asks to checkpoint, save state or update status in a research-kit project.
---

# Checkpoint

Updates the project's state files so the next session starts from where this one stopped. All paths are relative to `${CLAUDE_PROJECT_DIR}`. It commits the files it changed, and only those; it **never pushes**.

## Mode

`$ARGUMENTS` is `quick` (the default when empty) or `full`. Anything else: stop and ask.

## Identify the session

This conversation's session id is `${CLAUDE_SESSION_ID}`.
1. Read its start record, `state/.sessions/${CLAUDE_SESSION_ID}.json` (JSON with `session_id`, `started`, `source`, `code_head`, `paper_head`). The SessionStart hook writes it once per conversation and never rewrites it.
2. If the record is missing, or its `session_id` differs from `${CLAUDE_SESSION_ID}`, stop and report both ids, together with the latest id in `state/.session_id`. Don't guess. A missing record usually means session start's git checks ran out of time: `state/.hook.log` then has an `ERROR session id` line. Say so; the next resume or compaction writes the record, and its commit list starts there (step 3).
3. If `source` is not `startup` or `clear`, the record was first written when this conversation was resumed or compacted, so its commit list starts at `started`, not at the conversation's real start. Say so in the entry.
4. List this session's commits in each repo:
   ```
   git -C "${CLAUDE_PROJECT_DIR}" log --oneline --invert-grep --grep='^Checkpoint 20' <code_head>..HEAD
   git -C "${CLAUDE_PROJECT_DIR}/paper" log --oneline <paper_head>..HEAD
   ```
   A `null` head means the repo had no commits (or wasn't attached) at the start: list all of its commits. Skip the paper repo if `paper/` isn't attached. The checkpoint's own commits are left out.

## Quick mode

Update `state/CURRENT_STATE.md`. Its sections are fixed: Goal, Blocker, Next steps, Last 3 sessions. It holds no rules; rules belong in the project `CLAUDE.md` (see `/kit:learn`).

1. **Goal**: update only if it changed this session.
2. **Blocker**: what stops progress now, with the exact command that reproduces it, or `None.`
3. **Next steps**: a numbered list, first step first, concrete enough to start without rereading this conversation.
4. **Last 3 sessions**: newest first. This session's entry is keyed by its id. If an entry with this id exists, update it in place; otherwise add it at the top:
   ```
   ### YYYY-MM-DD — <session id>
   Done: <what was done>
   Commits (code): <short sha> <subject>; ... or none
   Commits (paper): <short sha> <subject>; ... or none
   Open threads: <what is unfinished or undecided>
   ```
   The date is the `started` date. With more than 5 commits in a repo, give the count and the 5 most recent.
5. **Archive**: move every entry beyond the newest three to the end of `state/archive/sessions-YYYY.md` (the entry's year), oldest first. Create the file with a `# Sessions YYYY` heading if it doesn't exist.
6. **Size**: run
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_state_size.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   and report the size against the allotment. Exit 1 (over budget): condense the session entries and Next steps, move anything worth keeping to the archive file, tell the user what was cut, and re-run. If it can only fit by cutting the Goal, the Blocker or live next steps, stop and ask. Exit 2: stop and ask.

## Full mode

Quick mode, then:

1. **Decisions**: for each decision made this session, propose an entry for `state/DECISIONS.md` and add it only with approval:
   ```
   ### D-NNN — Title (YYYY-MM-DD)
   **Decision:** ...
   **Rejected:** each alternative and why
   **Rationale:** ...
   ```
   NNN is the next number after the highest existing one. Then regenerate the index (never edit it by hand):
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" decisions_index.py --project "${CLAUDE_PROJECT_DIR}"
   ```
2. **Pointers**: run
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_pointers.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   Exit 1 lists paths cited in the state files or `CLAUDE.md` that don't exist: report each and fix it with approval.
3. **Ledger**: compare the generated table in `state/CLAIMS_LEDGER.md` with `numbers.tex` (the `numbers_tex` path in `.claude/research.yml`) by hand: the same macros, values, sources and commits. If `numbers.tex` doesn't exist yet, the table must be empty; report that the numbers haven't been generated. Report any mismatch. Never fix the generated table by hand; it is rewritten only by `numbers_build.py` (see `/kit:numbers`).
4. **Repos**: after the commit (see Commit below), report, for the code repo and `paper/`, the uncommitted files (`git status --short`) and the unpushed commits (`git log --oneline @{u}..HEAD`). A repo with no upstream (the code repo has none unless a backup remote was added) is reported as `no upstream`.
5. **Promotion candidates**: list rules in the project `CLAUDE.md` that look general, meaning they name no file, dataset or paper term, as candidates to promote with `/kit:learn`. Don't move them.
6. **Hook log**: trim `state/.hook.log` to its last 500 lines.
7. **Environments**: for each language in `research.yml`, report whether its dependencies and lockfile agree. Python: `uv lock --check` from the project root (exit 1 means `pyproject.toml` and `uv.lock` disagree). R: `Rscript -e 'renv::status()'` from the project root. It exits 0 either way, so read its output: anything other than "No issues found" is drift (for example, packages the code uses that aren't installed in the project library, or that `renv.lock` doesn't record). Report only; never run `uv lock`, `uv sync` or `renv::snapshot()` here.

## Commit

Commit, in the code repo, the files this skill changed: `state/CURRENT_STATE.md`, any `state/archive/sessions-YYYY.md` it wrote, and in full mode `state/DECISIONS.md` and any file a pointer fix touched. Never `state/.hook.log`, which git ignores. Name each path, so that other staged work stays out:
```
git -C "${CLAUDE_PROJECT_DIR}" add <paths>
git -C "${CLAUDE_PROJECT_DIR}" commit -m "Checkpoint <YYYY-MM-DD>" -- <paths>
```
- A named file is committed whole, including any earlier uncommitted edits to it. Say so in the report.
- If the hook printed `baseline lowered`, run `git -C "${CLAUDE_PROJECT_DIR}" add .lint_baseline_slides`, so that the index matches the commit.
- If approvals asked in this checkpoint are still open, commit what is done now and the rest once they are answered.
- Skip this if no file changed. If the commit fails, stop and report.

## Report

End with: the checkpoint commit, what changed in each state file, the size against the allotment, the review status line from `"${CLAUDE_PLUGIN_ROOT}/bin/kit" codex_review.py --project "${CLAUDE_PROJECT_DIR}" --status`, and in full mode the findings from steps 1–7.

## Done when
- [ ] This conversation's start record exists and matches its id, and its entry is added or updated in place.
- [ ] Goal, Blocker (with its command) and Next steps are current.
- [ ] At most three session entries remain; older ones are in `state/archive/`.
- [ ] `check_state_size.py` exits 0, and the size was reported.
- [ ] Full mode: approved decisions added and the index regenerated; pointers, ledger, repos, promotion candidates, the hook log and environments handled and reported.
- [ ] The files this skill changed are committed, and nothing else; nothing was pushed.

## Stop and ask
- `$ARGUMENTS` is not empty, `quick` or `full`.
- This conversation's start record is missing, or its id differs from `${CLAUDE_SESSION_ID}`.
- A script exits 2.
- `CURRENT_STATE.md` can only fit its allotment by cutting the Goal, the Blocker or live next steps.
