---
name: new-project
description: Use when the user wants to start a new research paper project with the research kit.
---

# New project

`$0` is the project name. Every step that changes anything outside the new project's folder needs the user's approval, except `kit setup`, which writes only the kit's own data folder.

## 1. Set up and scaffold

1. **The kit's environment:** run `"${CLAUDE_PLUGIN_ROOT}/bin/kit" setup`. It returns at once when the environment exists. The first time, it needs uv on the PATH and creates a small Python environment. If it reports uv missing, show the user its message and stop.
2. Ask the user which languages the paper uses (R, Python or both) and whether it has a package in either; there are no defaults.
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py new $0 --lang r --lang python --package r
   ```
   That example is a paper using both languages with an R package. `--package <lang>` implies `--lang <lang>`. If the scaffold says a derived package name isn't valid, ask for one and pass `--package <lang>=NAME`.

   The project goes in the folder that `projects_root` names in the personal `config.yml`. If the scaffold stops because none is set, ask the user for the parent folder and rerun with `--root <folder>`. The scaffold prints the project's path; `<project>` below means that path.

**Prerequisites:** R needs renv in the user's R library, and Python needs uv on the PATH. If the scaffold reports one missing, show the user its install command and stop; never install it yourself. On any refusal (exit 2), stop and ask. The scaffold can take several minutes (renv copies packages); run it with a long timeout, and if it is interrupted, rerun it — a failed or interrupted scaffold removes the partial project.

## 2. Overleaf (manual steps)

1. The user creates a new Overleaf project and copies its git URL (Overleaf menu, Git).
2. **Credentials, before the first clone.** Check for an existing helper:
   ```
   git config --global --get credential.https://git.overleaf.com.helper
   ```
   If it is already `store --file ~/.config/git/overleaf-credentials` (written with `~` or with the full home path), it is set up: continue. If none is set, propose this command and run it only with approval:
   ```
   mkdir -p ~/.config/git && git config --global credential.https://git.overleaf.com.helper "store --file ~/.config/git/overleaf-credentials"
   ```
   If a different helper is set, stop and ask.
3. **The user runs `attach-paper` in a separate terminal, outside Claude Code**, so the token goes in at git's prompt and never enters this conversation:
   ```
   cd <project> && "${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py attach-paper <overleaf-git-url>
   ```
   At the prompt: username `git`, password the Overleaf git token. Never ask for the token here. If it appears in the conversation anyway, tell the user to revoke it in Overleaf and create a new one.
4. Push the attach commit, with approval: `git -C <project>/paper push`.

## 3. Verify

1. **Fetch without a prompt**, as the SessionStart hook does:
   ```
   GIT_TERMINAL_PROMPT=0 git -C <project>/paper fetch
   ```
   It must exit 0 without asking for anything.
2. **Overleaf kept the dotfiles.** Clone fresh into a temporary directory and confirm that `.gitignore`, `.lint_baseline`, `.lint_baseline_tables`, `generated/.gitkeep`, `figures/.gitkeep` and `tables/.gitkeep` are all there. The three folders sit beside `numbers_tex`'s folder: at the clone's root by default, or in the manuscript's subfolder if `numbers_tex` points into one (`draft/generated/`). For the default layout:
   ```
   D=$(mktemp -d) && GIT_TERMINAL_PROMPT=0 git clone -q <overleaf-git-url> "$D/check" && ls -a "$D/check" "$D/check/generated" "$D/check/figures" "$D/check/tables"
   ```
   Then remove `$D`. If any file is missing, stop and report.
3. **Generate the inputs once**, so the paper and talks can `\input` them from day one:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" notation_tex.py --project <project>
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" numbers_build.py --project <project>
   ```
   Commit `generated/notation.tex` and `generated/numbers.tex` in the paper repo and push them with approval, and commit `state/CLAIMS_LEDGER.md` in the code repo.

## 4. Hand over

Tell the user:
- Start Claude Code from `<project>`; the kit is enabled there by `.claude/settings.json`.
- The paper's preamble needs `\input{generated/numbers.tex}` and `\input{generated/notation.tex}`. That is a manuscript edit, made through `/kit:writing`.
- Seed `notes/research_questions.md` with `/kit:notes`.
- A language or package can be added later from the project root: `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-language r|python`, or `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-package r|python [--name NAME]`.
- The paper's code, as it will be released, lives in the project's library: its package, or folders or files named in `library:` in `.claude/research.yml`. Pipeline scripts are thin drivers that call it; every number, date and path the code uses lives in `analysis/params.yml`. `/kit:code` reads both before writing code. A project made before these files existed gets them with `"${CLAUDE_PLUGIN_ROOT}/bin/kit" scaffold.py add-params`.

## Done when
- [ ] `kit setup` succeeded.
- [ ] `scaffold.py new` and `attach-paper` both succeeded, and the attach commit is pushed.
- [ ] The credential helper is scoped to `https://git.overleaf.com`, and the token never appeared in this conversation.
- [ ] The prompt-free fetch exits 0.
- [ ] A fresh clone contains all five dotfiles.
- [ ] `notation.tex` and `numbers.tex` exist and were committed, and pushed unless the user declined.

## Stop and ask
- `scaffold.py` refuses (exit 2), in `new` or `attach-paper`.
- A different credential helper is already set for Overleaf.
- The fetch prompts, fails or times out.
- A fresh clone lacks any of the dotfiles.
- `notation_tex.py` or `numbers_build.py` exits 2.
- renv or uv is missing.
- `kit setup` exits 2.
