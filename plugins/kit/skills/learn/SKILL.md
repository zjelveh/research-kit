---
name: learn
description: Use when the user corrects how Claude works, states a preference or lesson to keep, or asks to remember or learn something, in a research-kit project.
---

# Learn a lesson

Routes one lesson to the one place it belongs, with the user's approval.

## 1. Decide whether it is a lesson

The lesson is `$ARGUMENTS`; if that is empty, it is the latest correction in this conversation.

A correction about the current task is not a lesson. Record a standing rule only when the user says it should hold beyond this task, or confirms that when asked. If it's unclear, ask: "Should this hold from now on, or only for this task?" Never turn a one-off instruction into a standing rule.

## 2. Choose the level

| Level | Destination |
|---|---|
| Global, always on | the rules in effect: `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which rules` |
| Prose voice or word choice | the base voice: `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-voice` |
| Paragraph or section structure | the writing patterns: `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which writing-patterns` |
| Slide conventions | `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which slides-style` |
| Figure conventions | `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which figure-style` |
| Table settings a new paper starts from (star rule, decimals, brackets) | `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which table-style` |
| Specific to a venue | `"${CLAUDE_PLUGIN_ROOT}/bin/kit" which venue <venue>` |
| How a kit procedure works | the kit skill `${CLAUDE_PLUGIN_ROOT}/skills/<stream>/SKILL.md`, only when the kit folder is a git checkout (section 4) |
| Specific to a project | `${CLAUDE_PROJECT_DIR}/CLAUDE.md`, or `state/DECISIONS.md` for a decision |

- **When the level is unclear, default to project.** A wrong global rule affects every project.
- Always-on rules cost context in every session of every project; propose that level only for a rule that applies to nearly every task.
- A decision (a choice among alternatives for this paper) goes to `state/DECISIONS.md` in the `### D-NNN — Title (YYYY-MM-DD)` format with **Decision**, **Rejected** and **Rationale**, followed by `decisions_index.py` (see `/kit:checkpoint`).
- The first seven levels are personal files. When `kit which` prints a path in the kit's `defaults/` folder, first run `"${CLAUDE_PLUGIN_ROOT}/bin/kit" customize <item>` (for a venue, `customize venue <name>`), which copies the default into the personal folder, and edit that copy. Never edit the kit's `defaults/` for a lesson. A venue the kit doesn't have is created the same way. The table style is read entry by entry: the settings in effect are the personal file's entries over the kit's, so a personal copy may keep only the entries it changes. It applies when the table writer is added to a project (`add-tables`); a project's own settings are in its `analysis/params.yml`.

Propose the level with a one-line reason. The user decides.

## 3. Show the exact edit

1. Check that the lesson isn't already recorded, or contradicted, at another level. If it is, propose one home and the removal of the other copy.
2. Show the file, the location and the full before and after. Apply only after approval.

## 4. Apply

- **Personal rules**: after the edit, run `wc -c` on the file `kit which rules` printed. It must be at most 1536 bytes (`limits.yml: rules_cap_bytes`). If it's over, stop and ask what to cut; never shorten other rules on your own. Longer rules shrink CURRENT_STATE's allotment, so then run:
  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_state_size.py --project "${CLAUDE_PROJECT_DIR}"
  ```
- **Any personal file**: the personal folder is what `"${CLAUDE_PLUGIN_ROOT}/bin/kit" where` prints. If it is a git repo (`git -C <folder> rev-parse` exits 0), commit only that file there, with a message that cites the lesson; otherwise just save it. Rules take effect when the SessionStart hook next runs (a new conversation, a resume, `/clear` or a compaction); the voice, writing patterns, slide and figure conventions and venue take effect the next time a skill reads them.
- **A kit skill**: only when `[ "$(git -C "${CLAUDE_PLUGIN_ROOT}" rev-parse --show-toplevel)/plugins/kit" -ef "${CLAUDE_PLUGIN_ROOT}" ]` succeeds, meaning the kit is a checkout of its own repo that the user develops. If that repo has other uncommitted changes or isn't on `main`, stop and ask. Edit the skill with no attribution in the text (never "(user, date)"); the lesson and its date go in the commit message. Run `"${CLAUDE_PLUGIN_ROOT}/bin/kit" python -m pytest <repo>/tests/python/test_skills.py`; the kit's own environment may lack pytest, and then the test environment that `<repo>/bin/setup.sh` makes in `<repo>/.venv` runs it. Then commit only that file. A skill takes effect at the next session start, or after `/reload-plugins`. If the kit is an installed copy, updates overwrite it: offer the personal rules or the project's `CLAUDE.md` instead.
- **A project file** (`CLAUDE.md`, `state/DECISIONS.md`): commit only that file, in the project's code repo: `git add <file>`, then `git commit -m "<lesson>" -- <file>`.

Auto-memory is for personal context only, never for rules.

## Done when
- [ ] The user confirmed the lesson should hold beyond the current task.
- [ ] The level was approved, and the exact edit was shown and approved.
- [ ] The edit is applied in exactly one place, with no duplicate at another level.
- [ ] For the rules: at most 1536 bytes, and `check_state_size.py` exits 0.
- [ ] For a personal file: committed in the personal folder when it is a git repo.
- [ ] For a kit skill: `test_skills.py` passes, and it is committed alone with the lesson in the commit message, not in the text.
- [ ] For a project file: committed alone in the code repo.
- [ ] The user was told when it takes effect.

## Stop and ask
- It's unclear whether the correction should hold beyond the current task.
- The rules would exceed 1536 bytes.
- `check_state_size.py` exits 1 or 2 after a `rules.md` edit, or `test_skills.py` fails.
- The kit repo has other uncommitted changes or isn't on `main`.
- `kit which`, `kit customize` or `kit where` exits 2.
