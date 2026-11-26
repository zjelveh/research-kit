#!/usr/bin/env python3
"""Create a research-kit project (`new`), attach its Overleaf clone (`attach-paper`), add a language or package
(`add-language`, `add-package`), add the parameter files (`add-params`), start a talk (`new-talk`) and rewrite a
project's git hooks (`install-hooks`). Specs: kit design §5.7, §5.8; languages and packages §3; code §6."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import (CONFIG_REL, LANGUAGES, PLUGIN_ROOT, KitError, find_project, git, load_config,  # noqa: E402
                    package_name_problem, paper_folders, personal_config, personal_dir, stable_kit)
import lint_numbers  # noqa: E402

TEMPLATES = PLUGIN_ROOT / "templates"


def git_config(key: str) -> str:
    out = subprocess.run(["git", "config", "--get", key], capture_output=True, text=True).stdout.strip()
    if not out:
        raise KitError(f"git config {key} is not set; set it before scaffolding")
    return out


def render(text: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", text)))
    if left:
        raise KitError(f"unrendered template placeholders: {left}")
    return text


def copy_tree(src: Path, dst: Path, values: dict[str, str]) -> None:
    for path in sorted(src.rglob("*")):
        out = dst / render(str(path.relative_to(src)), values)
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(path.read_text(encoding="utf-8"), values), encoding="utf-8")


def hooks_dir(repo: Path) -> Path:
    """The repo's own hooks folder, <common git dir>/hooks, which its worktrees share. A repo with
    core.hooksPath set is refused: that folder may serve other repos, and the kit never writes there."""
    if git(repo, "config", "--get", "core.hooksPath", check=False).strip():
        raise KitError(f"{repo}: core.hooksPath is set; the kit installs its hook only in the repo's own "
                       "hooks folder, so unset it for this repo or add the hook by hand")
    common = Path(git(repo, "rev-parse", "--git-common-dir").strip())
    return (common if common.is_absolute() else Path(repo) / common).resolve() / "hooks"


def install_hook(repo: Path, project_dir: Path, gate: str) -> None:
    """The code repo's hook (gate slides) runs the code gate first; the paper clone's runs the paper gate."""
    code_gate = (f'"{stable_kit()}" lint_code.py --project "{project_dir}" --precommit || exit $?\n'
                 if gate == "slides" else "")
    text = render((TEMPLATES / "hooks" / "pre-commit").read_text(encoding="utf-8"),
                  {"KIT": str(stable_kit()), "PROJECT_DIR": str(project_dir), "GATE": gate, "CODE_GATE": code_gate})
    d = hooks_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    hook = d / "pre-commit"
    hook.write_text(text, encoding="utf-8")
    hook.chmod(0o755)


def set_group(root: Path, gid: int) -> None:
    for p in [root, *root.rglob("*")]:
        os.chown(p, -1, gid, follow_symlinks=False)
        if p.is_dir() and not p.is_symlink():
            p.chmod(p.stat().st_mode | stat.S_ISGID)


LANG_NAMES = {"r": "R", "python": "Python"}
# Paths each command creates. add-language/add-package refuse if any exists, and remove exactly
# these on failure (spec §3).
LANG_PATHS = {"r": [".Rprofile", "renv", "renv.lock", "analysis/numbers/make_numbers.R"],
              "python": ["pyproject.toml", "uv.lock", ".python-version", ".venv",
                         "analysis/numbers/make_numbers.py"]}
# The parameter files and their readers (code spec §2, §6). A file the kit wrote says research-kit in its
# first lines; one that doesn't is the project's own, which the kit never overwrites.
PARAM_FILES = ["analysis/params.yml", "analysis/explore/params.yml"]
READERS = {"r": "analysis/params.R", "python": "analysis/params.py"}
EXPLORE_OUT = "analysis/explore/out/"


def kits_file(path: Path) -> bool:
    return "research-kit" in "".join(path.read_text(encoding="utf-8", errors="replace").splitlines(True)[:5])


def write_reader(project: Path, lang: str) -> str | None:
    """Write the language's parameter reader unless the project has one; the path written, or None."""
    rel = READERS[lang]
    if (project / rel).exists():
        if not kits_file(project / rel):
            print(f"note: kept your own {rel}; the kit's param() reader needs that name, so rename yours and run "
                  "scaffold.py add-params")
        return None
    (project / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATES / "params" / Path(rel).name, project / rel)
    return rel
UNSTAGED = {".venv"}  # created but ignored by git
UV_ENV = {"UV_PYTHON_DOWNLOADS": "never", "UV_LINK_MODE": "copy"}
R_PKG_RULE = ('- After changing `pkg/r/`, run `renv::install("./pkg/r")` and `renv::snapshot()` '
              "before running analysis code.")
R_MISSING = (  # Run with --no-init-file, so .libPaths() is the user's library, not the project's.
    'own <- Sys.getenv("KIT_OWN_RPKG"); lib <- renv::paths$library(project = getwd()); '
    'cols <- c("Source", "Package"); d <- renv::dependencies(quiet = TRUE)[cols]; '
    'if (dir.exists("pkg/r")) d <- rbind(d, renv::dependencies("pkg/r", quiet = TRUE)[cols]); '
    'deps <- setdiff(unique(d$Package), c(own, "renv", rownames(installed.packages(priority = "base")))); '
    "have <- function(p) nzchar(system.file(package = p)) || dir.exists(file.path(lib, p)); "
    "missing <- deps[!vapply(deps, have, logical(1))]; "
    'if (length(missing)) { for (p in missing) cat(p, ": ", paste(unique(d$Source[d$Package == p]), '
    'collapse = ", "), "\\n", sep = ""); quit(status = 3) }')
R_SYNC = ('own <- Sys.getenv("KIT_OWN_RPKG"); '
          'if (nzchar(own)) { imp <- setdiff(unique(renv::dependencies("pkg/r", quiet = TRUE)$Package), '
          'c(own, "renv")); if (length(imp)) renv::hydrate(packages = imp, prompt = FALSE); '
          'renv::install("./pkg/r", prompt = FALSE) }; '
          "renv::hydrate(prompt = FALSE); renv::snapshot(prompt = FALSE); "
          "if (!isTRUE(renv::status()$synchronized)) { "
          'cat("KIT: renv::status() is not synchronized after hydrate and snapshot; '
          'a package could not be installed\\n"); quit(status = 4) }')


INSTALL_HINTS = {"uv": "install uv (https://docs.astral.sh/uv/getting-started/installation/)",
                 "Rscript": "install R (https://cran.r-project.org/)"}


def run(cmd: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> str:
    if shutil.which(cmd[0]) is None:
        raise KitError(f"{cmd[0]} is not on the PATH; {INSTALL_HINTS.get(cmd[0], 'install it')} and rerun")
    proc = subprocess.run(cmd, cwd=cwd, env=dict(os.environ, **(extra_env or {})),
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", (proc.stdout + proc.stderr).strip())
        raise KitError(f"{' '.join(cmd)} failed (exit {proc.returncode}) in {cwd}:\n{text}")
    return proc.stdout


def require_renv(project: Path) -> None:
    if shutil.which("Rscript") is None:
        raise KitError(f"Rscript is not on the PATH; {INSTALL_HINTS['Rscript']} and rerun")
    proc = subprocess.run(["Rscript", "--no-init-file", "-e",
                           'if (!requireNamespace("renv", quietly = TRUE)) quit(status = 3)'],
                          cwd=project, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode == 3:
        raise KitError("renv is not installed in your R library; install it once with "
                       "Rscript -e 'install.packages(\"renv\")' and rerun")
    if proc.returncode != 0:
        raise KitError(f"checking for renv failed:\n{(proc.stdout + proc.stderr).strip()}")


def require_renv_library_ignored(project: Path) -> None:
    if subprocess.run(["git", "-C", str(project), "check-ignore", "-q", "renv/library/x"]).returncode != 0:
        raise KitError("renv/library is not git-ignored (renv's renv/.gitignore missing?); "
                       "refusing to commit the library")


def r_init(project: Path) -> None:
    """renv::init(bare = TRUE): .Rprofile, renv/ (spec §4.2 step 1)."""
    require_renv(project)
    run(["Rscript", "--no-init-file", "-e", "renv::init(bare = TRUE)"], project)


def r_check_synced(project: Path) -> None:
    """Refuse to touch an R environment that is out of sync with renv.lock (spec §3)."""
    require_renv(project)
    proc = subprocess.run(["Rscript", "-e", "if (!isTRUE(renv::status()$synchronized)) quit(status = 4)"],
                          cwd=project, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode == 4:
        report = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", (proc.stdout + proc.stderr).strip())
        raise KitError("the R environment is out of sync with renv.lock (renv::status() below). Typical "
                       "fixes: renv::hydrate() or renv::install() for packages the code uses but the project "
                       "library lacks (including untracked scripts), then renv::snapshot(); or "
                       "renv::restore() to match renv.lock. Then rerun.\n" + report)
    if proc.returncode != 0:
        raise KitError(f"checking the R environment failed:\n{(proc.stdout + proc.stderr).strip()}")


def r_sync(project: Path, own: str | None) -> None:
    """Install the project's own R package (if any), hydrate from the user library, snapshot (§4.2)."""
    require_renv(project)
    env = {"KIT_OWN_RPKG": own or ""}
    proc = subprocess.run(["Rscript", "--no-init-file", "-e", R_MISSING], cwd=project,
                          env=dict(os.environ, **env), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    if proc.returncode == 3:
        raise KitError("R packages this project's code uses are in neither your R library nor the "
                       "project library:\n" + proc.stdout.strip()
                       + "\nInstall them first, or remove the code that uses them.")
    if proc.returncode != 0:
        raise KitError(f"checking R dependencies failed:\n{(proc.stdout + proc.stderr).strip()}")
    run(["Rscript", "-e", R_SYNC], project, env)


def py_init(project: Path) -> None:
    """uv lock + uv sync for the analysis environment (spec §4.1)."""
    run(["uv", "lock"], project, UV_ENV)
    run(["uv", "sync"], project, UV_ENV)


def py_install_pkg(project: Path) -> None:
    """Install pkg/python into the analysis environment, editable (spec §4.1)."""
    run(["uv", "add", "--no-workspace", "--editable", "./pkg/python"], project, UV_ENV)


def setup_language(project: Path, lang: str, packages: dict[str, str]) -> None:
    if lang == "python":
        py_init(project)
        if "python" in packages:
            py_install_pkg(project)
    else:
        r_init(project)
        r_sync(project, packages.get("r"))


def default_package_name(lang: str, project_name: str) -> str:
    if lang == "r":
        return re.sub(r"[-_]", "", project_name.lower())
    return project_name.lower().replace("-", "_")


def package_name(lang: str, project_name: str, override: str | None, hint: str) -> str:
    name = override or default_package_name(lang, project_name)
    problem = package_name_problem(lang, name)
    if problem:
        raise KitError(f"'{name}' is {problem}; " + ("choose another name" if override else f"pass {hint}"))
    if lang == "python" and re.sub(r"_+", "-", name) == analysis_dist_name(project_name):
        raise KitError(f"'{name}' collides with the analysis environment's project name; "
                       f"pass {hint} with another name")
    return name


def analysis_dist_name(project_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
    if not slug:
        raise KitError(f"cannot derive a Python project name from {project_name!r}")
    return f"{slug}-analysis"


def base_values(project_name: str) -> dict[str, str]:
    return {"PROJECT": project_name, "DATE": dt.date.today().isoformat(), "KIT": str(stable_kit()),
            "GIT_NAME": git_config("user.name"), "GIT_EMAIL": git_config("user.email"),
            "ANALYSIS_DIST": analysis_dist_name(project_name)}


def pkg_values(lang: str, name: str) -> dict[str, str]:
    return {"RPKG": name} if lang == "r" else {"PYPKG": name}


def flow_languages(langs: list[str]) -> str:
    return "[" + ", ".join(langs) + "]"


def flow_packages(packages: dict[str, str]) -> str:
    return "{" + ", ".join(f'{k}: "{v}"' for k, v in packages.items()) + "}"


def set_config_line(project: Path, key: str, value: str) -> None:
    cfg = project / CONFIG_REL
    text = cfg.read_text(encoding="utf-8")
    new, n = re.subn(rf"(?m)^{key}: .*$", f"{key}: {value}", text)
    if n != 1:
        raise KitError(f"{cfg}: expected exactly one '{key}: ...' line, found {n}")
    cfg.write_text(new, encoding="utf-8")


def add_rule(project: Path, rule: str) -> None:
    path = project / "CLAUDE.md"
    text = path.read_text(encoding="utf-8")
    if rule in text:
        return
    text = text.replace("(none yet)", rule, 1) if "(none yet)" in text else text.rstrip("\n") + "\n" + rule + "\n"
    path.write_text(text, encoding="utf-8")


def cmd_new(name: str, root: Path, langs: list[str], packages: dict[str, str | None] | None = None) -> Path:
    root = Path(root).resolve()
    """Languages keep their given order, then languages implied by packages are appended; the CLI passes
    them in first-named order via parse_specs."""
    packages = dict(packages or {})
    if not root.is_dir():
        raise KitError(f"--root {root} is not a directory")
    if not stable_kit().is_file():
        raise KitError(f"{stable_kit()} not found; run {PLUGIN_ROOT / 'bin' / 'kit'} setup first "
                       "(the pre-commit hook needs it)")
    if not name or name in (".", "..") or "/" in name:
        raise KitError(f"invalid project name {name!r}")
    target = root / name
    if target.exists():
        raise KitError(f"{target} already exists")
    langs = list(dict.fromkeys(list(langs) + list(packages)))  # --package <lang> implies --lang <lang>
    if not langs:
        raise KitError("give at least one language: --lang r|python, or --package r|python")
    for lang in langs:
        if lang not in LANGUAGES:
            raise KitError(f"unknown language {lang!r}; use r or python")
    names = {lang: package_name(lang, name, override, f"--package {lang}=NAME")
             for lang, override in packages.items()}
    if "python" in langs and shutil.which("uv") is None:
        raise KitError(f"uv is not on the PATH; {INSTALL_HINTS['uv']} and rerun")
    if "r" in langs:
        require_renv(root)
    values = base_values(name) | {"LANGUAGES": flow_languages(langs), "PACKAGES": flow_packages(names)}
    try:
        target.mkdir()
    except OSError as e:
        raise KitError(f"cannot create {target}: {e}") from None
    try:
        copy_tree(TEMPLATES / "project", target, values)
        (target / "notes" / "lit" / "pdfs").mkdir()  # ignored by git, so not in the template tree
        for lang in langs:
            copy_tree(TEMPLATES / "lang" / lang, target, values)
            write_reader(target, lang)
        for lang, pkg in names.items():
            copy_tree(TEMPLATES / "pkg" / lang, target / "pkg" / lang, values | pkg_values(lang, pkg))
        if "r" in names:
            add_rule(target, R_PKG_RULE)
        git(target, "init", "-q", "-b", "main")
        install_hook(target, target, "slides")
        for lang in langs:
            setup_language(target, lang, names)
        if "r" in langs:
            require_renv_library_ignored(target)
        git(target, "add", "-A")
        git(target, "commit", "-q", "-m", f"Scaffold {name} with research-kit")
        set_group(target, root.stat().st_gid)
    except BaseException as e:
        shutil.rmtree(target, ignore_errors=True)
        if isinstance(e, (KitError, OSError)):
            raise KitError(f"{e} — removed the partial project at {target}; fix and rerun") from None
        raise
    pk = ", ".join(f"{k}={v}" for k, v in names.items()) or "none"
    print(f"Created {target} (languages: {', '.join(langs)}; packages: {pk}).\n"
          f"Next: create the Overleaf project, then run\n"
          f"  {shlex.quote(str(stable_kit()))} scaffold.py attach-paper <overleaf-git-url> "
          f"--project {shlex.quote(str(target))}")
    return target


def parse_specs(specs: list[tuple[str, str]]) -> tuple[list[str], dict[str, str | None]]:
    """--lang/--package values in command-line order -> (languages in first-named order, packages)."""
    langs: list[str] = []
    packages: dict[str, str | None] = {}
    for kind, value in specs:
        lang, eq, override = value.partition("=") if kind == "package" else (value, "", "")
        if lang not in LANGUAGES:
            raise KitError(f"unknown language {lang!r} in --{kind}; use r or python")
        if kind == "package":
            if lang in packages:
                raise KitError(f"--package {lang} given twice")
            if eq and not override:
                raise KitError(f"--package {lang}= needs a name after '='")
            packages[lang] = override or None
        if lang not in langs:
            langs.append(lang)
    return langs, packages


def require_clean(project: Path) -> None:
    if git(project, "status", "--porcelain", "--untracked-files=no").strip():
        raise KitError(f"{project} has uncommitted changes to tracked files; commit them first, "
                       "so this command's commit holds only its own change")


def refuse_existing(project: Path, rels: list[str], cmd: str) -> None:
    for rel in rels:
        path = project / rel
        if path.exists() or path.is_symlink():
            raise KitError(f"{path} already exists; {cmd} never edits or deletes a file it didn't make")


OWN_TRACKED = [str(CONFIG_REL), "CLAUDE.md", ".gitignore", "pyproject.toml", "uv.lock", "renv.lock"]


def require_toplevel(project: Path) -> None:
    top = Path(git(project, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != project:
        raise KitError(f"{project} is not the top of its own git repository (git would act on {top})")


def refuse_hidden_tracked(project: Path) -> None:
    hidden = [e[2:] for e in git(project, "ls-files", "-v", "-z").split("\0")
              if e and (e[0].islower() or e[0] == "S")]
    if hidden:
        raise KitError(f"{project} has assume-unchanged or skip-worktree files, whose changes git would "
                       f"not see: {', '.join(hidden)}; clear them (git update-index --no-assume-unchanged "
                       "--no-skip-worktree) and rerun")


def require_flow_config(project: Path) -> None:
    cfg = project / CONFIG_REL
    text = cfg.read_text(encoding="utf-8")
    for key, opener in (("languages", "["), ("packages", "{")):
        lines = re.findall(rf"(?m)^{key}: .*$", text)
        if len(lines) != 1 or not lines[0][len(key) + 2:].lstrip().startswith(opener):
            raise KitError(f'{cfg}: write languages: and packages: each on one line, '
                           'e.g. languages: [r] and packages: {r: "mypkg"}')


def refuse_ignored(project: Path, paths: list[str]) -> None:
    """Refuse, before anything changes, a path that `git add` would refuse: one an ignore rule covers, or one
    inside an ignored folder, which git won't stage even when it tracks the file. A `!` exception counts."""
    probes = [f"{rel}/.kit-probe" if rel == "renv" or rel.startswith("pkg/") else rel
              for rel in paths if rel not in UNSTAGED]
    for rel in probes:
        dry = subprocess.run(["git", "-C", str(project), "add", "--dry-run", "--ignore-missing", "--", rel],
                             capture_output=True, text=True)
        if dry.returncode != 0:
            proc = subprocess.run(["git", "-C", str(project), "check-ignore", "-v", "--no-index", "--", rel],
                                  capture_output=True, text=True)
            rule = proc.stdout.split("\t")[0] if proc.returncode == 0 else dry.stderr.strip().splitlines()[0]
            raise KitError(f"{rel.removesuffix('/.kit-probe')} would be ignored by git ({rule}); fix the ignore "
                           "rule first. A file inside an ignored folder can't be staged even when git tracks it: "
                           "ignore the folder's contents instead (`folder/*`) and add a `!` line for the file")


def require_slides_gate_passing(project: Path, cfg: dict) -> None:
    count, baseline, _ = lint_numbers.run_gate(project, cfg, "slides", "index")
    if count > baseline:
        raise KitError(f"the slides numbers check already fails at HEAD ({count} > {baseline}); "
                       "fix that first, or this commit would be blocked")


def in_head(project: Path, rel: str) -> bool:
    return subprocess.run(["git", "-C", str(project), "cat-file", "-e", f"HEAD:{rel}"],
                          capture_output=True).returncode == 0


def rollback(project: Path, own: list[str], created: list[str]) -> None:
    """Undo only this command's own files; never reset --hard or clean, so other edits stay."""
    git(project, "reset", "-q", "--", *own)
    for rel in own:
        if in_head(project, rel):
            git(project, "checkout", "HEAD", "--", rel)
    for rel in created:
        path = project / rel
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
    for rel in ("pkg", "analysis/numbers"):
        d = project / rel
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()  # this command left it empty


def _add(project: Path, lang: str, override: str | None, package: bool) -> None:
    project = Path(project).resolve()
    if lang not in LANGUAGES:
        raise KitError(f"unknown language {lang!r}; use r or python")
    cfg = load_config(project)
    langs, pkgs = list(cfg["languages"]), dict(cfg["packages"])
    need_lang = lang not in langs
    cmd = f"add-{'package' if package else 'language'} {lang}"
    if not package and not need_lang:
        raise KitError(f"'{lang}' is already in languages in {project / CONFIG_REL}")
    if package and lang in pkgs:
        raise KitError(f"a {LANG_NAMES[lang]} package ({pkgs[lang]}) already exists in packages")
    require_toplevel(project)
    require_clean(project)
    refuse_hidden_tracked(project)
    created = (LANG_PATHS[lang] if need_lang else []) + ([f"pkg/{lang}"] if package else [])
    refuse_existing(project, created, cmd)
    if need_lang and not (project / READERS[lang]).exists():
        created.append(READERS[lang])
    pkg = package_name(lang, project.name, override, "--name NAME") if package else None
    require_flow_config(project)
    if lang == "python":
        if shutil.which("uv") is None:
            raise KitError(f"uv is not on the PATH; {INSTALL_HINTS['uv']} and rerun")
    else:
        require_renv(project)
    if lang == "r" and not need_lang:
        r_check_synced(project)  # refuse drift before creating anything (review I3)
    own = list(dict.fromkeys([rel for rel in OWN_TRACKED if in_head(project, rel)] + created))
    refuse_ignored(project, own)
    require_slides_gate_passing(project, cfg)
    values = base_values(project.name)
    orig = git(project, "rev-parse", "HEAD").strip()
    try:
        if need_lang:
            copy_tree(TEMPLATES / "lang" / lang, project, values)
            write_reader(project, lang)
            langs.append(lang)
            set_config_line(project, "languages", flow_languages(langs))
        if package:
            copy_tree(TEMPLATES / "pkg" / lang, project / "pkg" / lang, values | pkg_values(lang, pkg))
            pkgs[lang] = pkg
            set_config_line(project, "packages", flow_packages(pkgs))
            if lang == "r":
                add_rule(project, R_PKG_RULE)
        load_config(project)  # the edited file must still validate
        if need_lang:
            setup_language(project, lang, {lang: pkg} if package else {})
        elif lang == "python":
            py_install_pkg(project)
        else:
            r_sync(project, pkg)
        if need_lang and lang == "r":
            require_renv_library_ignored(project)
        outside = [f for f in git(project, "diff", "--name-only", "HEAD").splitlines()
                   if f not in own and not any(f.startswith(rel + "/") for rel in created)]
        if outside:
            raise KitError(f"tracked files outside {cmd} changed while it ran: {', '.join(outside)}; "
                           "nothing was committed and those edits are untouched")
        git(project, "add", "--", *[rel for rel in own if rel not in UNSTAGED and (project / rel).exists()])
        what = f"package {pkg}" if package else "environment"
        git(project, "commit", "-q", "-m", f"Add {LANG_NAMES[lang]} {what} (research-kit)")
    except BaseException as e:
        err = str(e) or type(e).__name__
        head = git(project, "rev-parse", "HEAD").strip()
        if head != orig:  # the commit landed: there is nothing to undo
            if isinstance(e, (KitError, OSError)):
                raise KitError(f"{err} — the commit {head[:7]} already landed, so nothing was rolled back") from None
            print(f"{cmd}: interrupted after commit {head[:7]} landed; nothing was rolled back", file=sys.stderr)
            raise
        try:
            rollback(project, own, created)
        except (KitError, OSError) as re_:
            keep = [rel for rel in own if in_head(project, rel)]
            raise KitError(f"{err}; ROLLBACK FAILED: {re_}. To undo by hand: git -C {project} reset -q -- "
                           f"{' '.join(own)}, then git -C {project} checkout HEAD -- {' '.join(keep)}, "
                           f"then remove {', '.join(created)}") from None
        if isinstance(e, (KitError, OSError)):
            raise KitError(f"{err} — rolled back {cmd}; fix and rerun") from None
        raise
    sha = git(project, "rev-parse", "HEAD").strip()
    subject = git(project, "log", "-1", "--format=%s").strip()
    print(f"{cmd}: committed {sha[:7]} '{subject}' in {project} (not pushed)")
    if package and need_lang:
        print(f"also added {LANG_NAMES[lang]} to languages")
    if package and lang == "r":
        print('R loads the installed copy: after changing pkg/r/, run renv::install("./pkg/r") and '
              "renv::snapshot() (rule added to CLAUDE.md)")
    if lang == "python":
        print("run code with: uv run --locked python ...")
    else:
        print("renv.lock records packages used by any R script in the project, including untracked ones")


def cmd_add_language(lang: str, project: Path) -> None:
    _add(project, lang, None, package=False)


def cmd_add_package(lang: str, project: Path, name: str | None = None) -> None:
    _add(project, lang, name, package=True)


def cmd_add_params(project: Path) -> list[str]:
    """Bring a project made before the code spec up to it (code spec §6): write the parameter files and the
    readers for its languages that it lacks, refresh any kit reader from an older kit (whatever its
    language), ignore analysis/explore/out/, and commit only those files; then rewrite the code repo's kit
    hook so the code gate runs. A file of the same name that the kit didn't
    write is the project's own: nothing is written, and the user renames it first."""
    project = find_project(Path(os.path.abspath(project)))
    require_toplevel(project)
    cfg = load_config(project)
    wanted = {rel: TEMPLATES / "project" / rel for rel in PARAM_FILES}
    wanted |= {rel: TEMPLATES / "params" / Path(rel).name for lang, rel in READERS.items()
               if lang in cfg["languages"]}
    # a kit reader already there is kept current even for a language the project doesn't declare
    wanted |= {rel: TEMPLATES / "params" / Path(rel).name for rel in READERS.values()
               if rel not in wanted and (project / rel).exists() and kits_file(project / rel)}
    foreign = [rel for rel in wanted if (project / rel).exists() and not kits_file(project / rel)]
    if foreign:
        raise KitError(f"{', '.join(foreign)} already exist{'s' if len(foreign) == 1 else ''} and "
                       f"{'is' if len(foreign) == 1 else 'are'} not the kit's; rename or move "
                       f"{'it' if len(foreign) == 1 else 'them'}, then rerun add-params")
    created = [rel for rel in wanted if not (project / rel).exists()]
    stale = []                                     # kit readers from an older kit, refreshed unless being edited
    for rel in (r for r in wanted if r in READERS.values() and (project / r).exists()):
        if git(project, "status", "--porcelain", "--", rel).strip():
            print(f"add-params: {rel} has uncommitted changes, so it was left as it is")
        elif (project / rel).read_bytes() != wanted[rel].read_bytes():
            stale.append(rel)
    refuse_ignored(project, created + stale)
    for rel in stale:
        shutil.copyfile(wanted[rel], project / rel)
        print(f"add-params: updated the kit's reader {rel} to this kit version")
    created += stale
    for rel in created:
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wanted[rel], project / rel)
    ignore = project / ".gitignore"
    probe = subprocess.run(["git", "-C", str(project), "check-ignore", "-q", "--no-index", EXPLORE_OUT + "x"])
    if probe.returncode != 0:
        if git(project, "status", "--porcelain", "--", ".gitignore").strip():
            print(f"add-params: .gitignore has uncommitted changes, so add the line {EXPLORE_OUT} to it yourself")
        else:
            text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
            ignore.write_text(text + ("" if not text or text.endswith("\n") else "\n") + EXPLORE_OUT + "\n",
                              encoding="utf-8")
            created.append(".gitignore")
    if created:
        git(project, "add", "--", *created)
        git(project, "commit", "-q", "-m", "Add the parameter files and readers (research-kit)", "--", *created)
        print(f"add-params: committed {', '.join(created)} in {project} (not pushed)")
    else:
        print("add-params: the parameter files, readers and ignore line are all there")
    try:                                  # the files are committed; the hook is a further step that may not apply
        main_checkout = main_checkout_if_linked(project)
        if main_checkout is not None:
            print(f"add-params: this is a linked worktree, whose hook is its main checkout's; run scaffold.py "
                  f"install-hooks there ({main_checkout}) to turn the code gate on")
        elif kit_hook(project) is not None:
            install_hook(project, project, "slides")
            print(f"add-params: the code gate is on in {hooks_dir(project) / 'pre-commit'}")
        else:
            print("add-params: no kit hook in this repo, so the code gate is off; run scaffold.py install-hooks "
                  "from the project's main checkout")
    except KitError as e:
        print(f"add-params: the code gate is off: {e}")
    return created


def set_paper_branch(project: Path, branch: str) -> None:
    cfg = project / ".claude" / "research.yml"
    text = cfg.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^paper_branch: .*$", f"paper_branch: {branch}", text)
    if n != 1:
        raise KitError(f"{cfg}: expected exactly one 'paper_branch:' line, found {n}")
    cfg.write_text(new, encoding="utf-8")
    print(f"research.yml: paper_branch set to {branch} (uncommitted in the code repo)")


def kit_hook(repo: Path) -> Path | None:
    """The repo's pre-commit hook if research-kit installed it (the last step of a successful attach)."""
    try:
        hook = hooks_dir(repo) / "pre-commit"
    except KitError:
        return None
    if hook.is_file() and "research-kit" in hook.read_text(encoding="utf-8", errors="replace"):
        return hook
    return None


def reusable_clone(paper: Path, url: str) -> bool:
    """True for a clone an earlier attach-paper kept after stopping: origin is `url`, nothing changed, no kit
    hook yet. Rerunning then needs no second clone, so no second token prompt. Scaffold files already on
    Overleaf (a paper attached before) don't count as attached: only the local hook does."""
    try:
        top = Path(git(paper, "rev-parse", "--show-toplevel").strip()).resolve()
        origin = git(paper, "remote", "get-url", "origin").strip()
        changes = git(paper, "status", "--porcelain", "--ignored").strip()
    except KitError:
        return False
    return top == paper and origin == url and not changes and kit_hook(paper) is None


def restore_clone(paper: Path, start: str, created: list[Path]) -> None:
    """Undo this run's changes to the clone: its commit, .gitignore edit, created files and hook. The clone
    was clean (fresh or checked) when the run began, so only this run's own changes are touched; -x because
    the clone's .gitignore may ignore a folder this run created."""
    hook = kit_hook(paper)
    if hook:
        hook.unlink()
    git(paper, "reset", "-q", "--hard", start)
    existing = [str(p.relative_to(paper)) for p in created if p.exists()]
    if existing:
        git(paper, "clean", "-q", "-fdx", "--", *existing)


def cmd_attach(url: str, project: Path) -> Path:
    project = Path(project).resolve()
    cfg = load_config(project)
    paper = (project / cfg["paper_dir"]).resolve()
    folders = paper_folders(project, cfg, paper)
    _, globs, base_rel = lint_numbers.gate_paths(project, cfg, "paper")
    if paper.exists():
        if not reusable_clone(paper, url):
            raise KitError(f"{paper} already exists (a rerun reuses it only if it is an untouched clone of {url}: "
                           "same origin, no changes, not attached yet)")
        print(f"Reusing the clone at {paper}, kept by an earlier attach-paper")
    else:
        proc = subprocess.run(["git", "clone", url, str(paper)])  # interactive: first clone may prompt for the token
        if proc.returncode != 0:
            raise KitError(f"git clone {url} failed (exit {proc.returncode}); see the message above")
    start = git(paper, "rev-parse", "HEAD").strip()
    created = [d for d in folders if not d.exists()] + [p for p in [paper / base_rel] if not p.exists()]
    try:
        branch = git(paper, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch != cfg["paper_branch"]:
            set_paper_branch(project, branch)
            cfg = load_config(project)
        files = lint_numbers.collect(paper, globs, "worktree")
        if not files:
            raise KitError(f"no files match lint.paper.globs {globs} in the clone; edit .claude/research.yml")
        for d in folders:
            if not (d / ".gitkeep").exists():
                created.append(d / ".gitkeep")
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
        ignore = paper / ".gitignore"
        wanted = (TEMPLATES / "paper.gitignore").read_text(encoding="utf-8").splitlines()
        have = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
        if not ignore.exists():
            created.append(ignore)
        ignore.write_text("\n".join(have + [w for w in wanted if w not in have]) + "\n", encoding="utf-8")
        count = sum(len(lint_numbers.lint_text(t, n)) for n, t in files.items())
        (paper / base_rel).write_text(f"{count}\n", encoding="utf-8")
        git(paper, "add", "-A")
        if git(paper, "status", "--porcelain").strip():   # a paper attached before may need nothing new
            git(paper, "commit", "-q", "-m",
                "Add research-kit scaffolding (generated/, figures/, tables/, .gitignore, numbers baseline)")
        install_hook(paper, project, "paper")
    except BaseException as e:
        try:
            restore_clone(paper, start, created)
            kept = (f"kept the clone at {paper}, unchanged; fix that and rerun the same attach-paper command, "
                    "which reuses it")
        except (KitError, OSError) as r:
            kept = f"could not undo this run's changes in {paper} ({r}); delete {paper} and rerun attach-paper"
        if isinstance(e, (KitError, OSError)):
            raise KitError(f"{e} — {kept}") from None
        print(f"attach-paper: {kept}", file=sys.stderr)
        raise
    print(f"Attached {paper} (branch {branch}, numbers baseline {count}). Committed locally, NOT pushed.\n"
          f"Review, then push with: git -C {paper} push\n"
          f"Optional GitHub backup: git -C {paper} remote add github <url> && git -C {paper} push github {branch}")
    return paper


TALK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
LATEX_SPECIAL = re.compile(r"[%#{}\\$&^~]")


def cmd_new_talk(talk: str, project: Path) -> Path:
    """slides/<talk>/talk.tex from the Beamer template, with relative paths to the paper's generated inputs,
    figures/ and tables/ taken from research.yml, so a manuscript in a subfolder (draft/) works too."""
    if not TALK_NAME.fullmatch(talk):
        raise KitError(f"talk name {talk!r}: use letters, digits, '.', '_' and '-', starting with a letter or digit")
    project = Path(os.path.abspath(project))  # not resolved: the paths in talk.tex follow the project's own layout
    cfg = load_config(project)
    paper = (project / cfg["paper_dir"]).resolve()
    if not paper.is_dir():
        raise KitError(f"{cfg['paper_dir']}/ isn't attached; run attach-paper first")
    out = project / "slides" / talk / "talk.tex"
    if out.exists():
        raise KitError(f"{out} already exists")
    *_, figures, tables = paper_folders(project, cfg, paper)

    def rel(path: Path) -> str:
        return Path(os.path.relpath(path, out.parent)).as_posix()

    values = {"FIGURES": rel(project / cfg["paper_dir"] / figures.relative_to(paper)),
              "TABLES": rel(project / cfg["paper_dir"] / tables.relative_to(paper)),
              "NUMBERS_TEX": rel(project / cfg["numbers_tex"]), "NOTATION_TEX": rel(project / cfg["notation_tex"])}
    bad = {k: v for k, v in values.items() if LATEX_SPECIAL.search(v)}
    if bad:
        raise KitError(f"a path to the paper contains a LaTeX special character: {bad}")
    text = render((TEMPLATES / "beamer" / "talk.tex").read_text(encoding="utf-8"), values)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise KitError(f"cannot create {out.parent}: {e}") from None
    created = False
    try:
        with open(out, "x", encoding="utf-8") as fh:
            created = True
            fh.write(text)
    except FileExistsError:
        raise KitError(f"{out} already exists") from None
    except OSError as e:
        if created:
            with contextlib.suppress(OSError):
                out.unlink()
        raise KitError(f"cannot write {out}: {e}") from None
    print(f"Created {out}")
    return out


def default_root() -> Path:
    root = personal_config().get("projects_root")
    cfg = personal_dir() / "config.yml"
    if not root:
        raise KitError(f"no folder for new projects: pass --root <folder>, or set projects_root in {cfg}")
    path = Path(str(root)).expanduser()
    if not path.is_absolute():
        raise KitError(f"projects_root in {cfg} must be an absolute path, got {root!r}")
    if not path.is_dir():
        raise KitError(f"projects_root {path} (from {cfg}) is not a directory")
    return path


def main_checkout_if_linked(repo: Path) -> Path | None:
    """The main checkout when `repo` is a linked worktree, else None. A worktree shares the main checkout's
    hooks, so a hook written from it would carry the worktree's path (shareable-kit spec §4)."""
    common = hooks_dir(repo).parent
    if Path(git(repo, "rev-parse", "--absolute-git-dir").strip()).resolve() != common:
        return common.parent
    return None


def cmd_install_hooks(project: Path) -> list[Path]:
    """Rewrite the kit's git hooks to call the stable launcher: the code repo's (slides gate) and, once the
    paper is attached, the clone's (paper gate). Run it on a project's main checkout, not a worktree."""
    project = find_project(Path(os.path.abspath(project)))
    if (main_checkout := main_checkout_if_linked(project)) is not None:
        raise KitError(f"{project} is a linked worktree; its hooks are its main checkout's, so run "
                       f"install-hooks there ({main_checkout})")
    cfg = load_config(project)
    targets = [(project, "slides")]
    paper = project / cfg["paper_dir"]
    if (paper / ".git").exists():
        targets.append((paper, "paper"))
    todo = []
    for repo, gate in targets:            # check every hook before writing any
        hook = hooks_dir(repo) / "pre-commit"
        ours = kit_hook(repo) is not None
        if hook.exists() and not ours:
            raise KitError(f"{hook} is not the kit's hook; leaving it alone")
        if gate == "paper" and not ours:
            print(f"skipped {hook}: no kit hook there yet; attach-paper installs it as its last step")
            continue
        todo.append((repo, gate, hook))
    for repo, gate, hook in todo:
        install_hook(repo, project, gate)
        print(f"installed {hook}")
    missing = [rel for rel in [*PARAM_FILES, *(READERS[lang] for lang in cfg["languages"])]
               if not (project / rel).exists()]
    if missing:
        print(f"note: the code gate is on, but {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing; "
              "run scaffold.py add-params so that param() exists")
    return [hook for _, _, hook in todo]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("name")
    n.add_argument("--root", type=Path)
    n.add_argument("--lang", dest="specs", action="append", metavar="LANG", type=lambda s: ("lang", s),
                   help="r or python; repeat for both")
    n.add_argument("--package", dest="specs", action="append", metavar="LANG[=NAME]", type=lambda s: ("package", s),
                   help="r or python, optionally =NAME; implies --lang")
    at = sub.add_parser("attach-paper")
    at.add_argument("url")
    at.add_argument("--project", type=Path, default=Path.cwd())
    al = sub.add_parser("add-language")
    al.add_argument("lang", choices=LANGUAGES)
    al.add_argument("--project", type=Path, default=Path.cwd())
    ak = sub.add_parser("add-package")
    ak.add_argument("lang", choices=LANGUAGES)
    ak.add_argument("--name")
    ak.add_argument("--project", type=Path, default=Path.cwd())
    nt = sub.add_parser("new-talk")
    nt.add_argument("talk")
    nt.add_argument("--project", type=Path, default=Path.cwd())
    ih = sub.add_parser("install-hooks")
    ih.add_argument("--project", type=Path, default=Path.cwd())
    ap_ = sub.add_parser("add-params")
    ap_.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            langs, packages = parse_specs(a.specs or [])
            cmd_new(a.name, a.root or default_root(), langs, packages)
        elif a.cmd == "attach-paper":
            cmd_attach(a.url, a.project)
        elif a.cmd == "add-language":
            cmd_add_language(a.lang, a.project)
        elif a.cmd == "new-talk":
            cmd_new_talk(a.talk, a.project)
        elif a.cmd == "install-hooks":
            cmd_install_hooks(a.project)
        elif a.cmd == "add-params":
            cmd_add_params(a.project)
        else:
            cmd_add_package(a.lang, a.project, a.name)
    except KitError as e:
        print(f"scaffold: ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
