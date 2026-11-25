import re
import shutil
import subprocess

import pytest

import scaffold
from build_fixture import write
from kitlib import KitError, load_config
from scaffold import R_PKG_RULE, cmd_add_language, cmd_add_package, cmd_add_params, cmd_new, main


def sh(p, *args):
    return subprocess.run(["git", "-C", str(p), *args], capture_output=True, text=True, check=True).stdout


def commits(p):
    return len(sh(p, "log", "--oneline").splitlines())


def test_add_language_python(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_add_language("python", p)
    assert load_config(p)["languages"] == ["r", "python"]
    files = set(sh(p, "ls-files").splitlines())
    assert {"pyproject.toml", "uv.lock", ".python-version", "analysis/numbers/make_numbers.py"} <= files
    assert commits(p) == 2 and "Add Python environment" in sh(p, "log", "-1", "--format=%s")
    assert sh(p, "status", "--porcelain") == ""


def test_add_package_r_to_r_project(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_add_package("r", p)
    assert load_config(p)["packages"] == {"r": "demo"}
    assert (p / "pkg/r/DESCRIPTION").is_file() and R_PKG_RULE in (p / "CLAUDE.md").read_text()
    assert '"demo"' in (p / "renv.lock").read_text()
    assert commits(p) == 2 and sh(p, "status", "--porcelain") == ""


def test_add_package_adds_language_in_one_commit(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_add_package("python", p, "colinf")
    cfg = load_config(p)
    assert cfg["languages"] == ["r", "python"] and cfg["packages"] == {"python": "colinf"}
    assert (p / "pkg/python/src/colinf/__init__.py").is_file()
    assert commits(p) == 2 and "Add Python package colinf" in sh(p, "log", "-1", "--format=%s")


def test_refuses_existing_language(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    with pytest.raises(KitError, match="already in languages"):
        cmd_add_language("r", p)


def test_refuses_existing_package(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"], {"r": None})
    with pytest.raises(KitError, match="already exists in packages"):
        cmd_add_package("r", p)


def test_refuses_dirty_tree(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "CLAUDE.md", "changed\n")
    with pytest.raises(KitError, match="uncommitted changes to tracked files"):
        cmd_add_language("python", p)


def test_untracked_files_allowed_and_left_alone(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "notes" / "scratch.md", "mine\n")
    cmd_add_language("python", p)
    assert "?? notes/scratch.md" in sh(p, "status", "--porcelain")


def test_refuses_existing_path_and_leaves_it(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "pyproject.toml", "mine\n")
    with pytest.raises(KitError, match="pyproject.toml already exists"):
        cmd_add_language("python", p)
    assert (p / "pyproject.toml").read_text() == "mine\n"


def test_failure_rolls_back_package_and_language(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    head = sh(p, "rev-parse", "HEAD")
    monkeypatch.setattr(scaffold, "py_install_pkg", lambda project: (_ for _ in ()).throw(KitError("uv boom")))
    with pytest.raises(KitError, match="uv boom.*rolled back"):
        cmd_add_package("python", p)
    for rel in ("pkg/python", "pyproject.toml", "uv.lock", ".python-version", ".venv",
                "analysis/numbers/make_numbers.py"):
        assert not (p / rel).exists(), rel
    assert sh(p, "rev-parse", "HEAD") == head and sh(p, "status", "--porcelain") == ""
    assert load_config(p)["languages"] == ["r"]


def test_failure_restores_tracked_files_changed_by_tools(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["python"])
    before = (p / "pyproject.toml").read_text()

    def install_then_fail(project):
        (project / "pyproject.toml").write_text(before + "\n# edited by uv\n")
        raise KitError("late boom")
    monkeypatch.setattr(scaffold, "py_install_pkg", install_then_fail)
    with pytest.raises(KitError, match="late boom"):
        cmd_add_package("python", p)
    assert (p / "pyproject.toml").read_text() == before
    assert sh(p, "status", "--porcelain") == ""


def test_block_style_config_refused_and_rolled_back(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    cfg = p / ".claude" / "research.yml"
    cfg.write_text(cfg.read_text().replace("languages: [r]", "languages:\n  - r"))
    sh(p, "commit", "-qam", "block style")
    with pytest.raises(KitError, match="each on one line"):
        cmd_add_language("python", p)
    assert not (p / "pyproject.toml").exists() and sh(p, "status", "--porcelain") == ""


def test_add_package_r_refuses_out_of_sync_env(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    monkeypatch.setattr(scaffold, "r_check_synced", lambda project: (_ for _ in ()).throw(KitError("the R environment is out of sync with renv.lock")))
    with pytest.raises(KitError, match="out of sync") as e:
        cmd_add_package("r", p)
    assert "rolled back" not in str(e.value)
    assert not (p / "pkg").exists() and sh(p, "status", "--porcelain") == ""


def test_cli(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    assert main(["add-language", "python", "--project", str(p)]) == 0
    assert main(["add-package", "python", "--name", "colinf", "--project", str(p)]) == 0
    assert load_config(p)["packages"] == {"python": "colinf"}


def test_keyboard_interrupt_rolls_back_and_reraises(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    head = sh(p, "rev-parse", "HEAD")
    monkeypatch.setattr(scaffold, "py_install_pkg", lambda project: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        cmd_add_package("python", p)
    assert not (p / "pkg").exists() and not (p / "pyproject.toml").exists()
    assert sh(p, "rev-parse", "HEAD") == head and sh(p, "status", "--porcelain") == ""


def test_concurrent_edit_to_other_tracked_file_is_kept(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    head = sh(p, "rev-parse", "HEAD")

    def edit_then_init(project):
        (project / "notes" / "research_questions.md").write_text("edited meanwhile\n")
        write(project / "uv.lock", "version = 1\n")
    monkeypatch.setattr(scaffold, "py_init", edit_then_init)
    with pytest.raises(KitError, match="changed while it ran"):
        cmd_add_language("python", p)
    assert (p / "notes" / "research_questions.md").read_text() == "edited meanwhile\n"
    assert sh(p, "rev-parse", "HEAD") == head
    assert sh(p, "status", "--porcelain").strip() == "M notes/research_questions.md"
    assert not (p / "pyproject.toml").exists() and not (p / "uv.lock").exists()
    assert load_config(p)["languages"] == ["r"]


def test_commit_landed_then_interrupt_rolls_nothing_back(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    head = sh(p, "rev-parse", "HEAD")
    real_git = scaffold.git

    def git_then_interrupt(repo, *args, **kw):
        out = real_git(repo, *args, **kw)
        if args and args[0] == "commit":
            raise KeyboardInterrupt
        return out
    monkeypatch.setattr(scaffold, "git", git_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        cmd_add_language("python", p)
    assert sh(p, "rev-parse", "HEAD") != head
    assert (p / "pyproject.toml").is_file() and (p / "uv.lock").is_file()
    assert load_config(p)["languages"] == ["r", "python"]
    assert sh(p, "status", "--porcelain") == ""


def test_rollback_failure_is_reported_with_manual_undo(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    lock = p / ".git" / "index.lock"

    def lock_then_fail(project):
        lock.write_text("")
        raise KitError("uv boom")
    monkeypatch.setattr(scaffold, "py_init", lock_then_fail)
    try:
        with pytest.raises(KitError) as e:
            cmd_add_language("python", p)
    finally:
        lock.unlink(missing_ok=True)
    assert "uv boom" in str(e.value) and "ROLLBACK FAILED" in str(e.value) and re.search(r"To undo by hand: git -C \S+ reset -q -- .*checkout HEAD", str(e.value))


def test_add_language_r_failure_rolls_back(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["python"])
    head = sh(p, "rev-parse", "HEAD")
    monkeypatch.setattr(scaffold, "r_sync", lambda project, own: (_ for _ in ()).throw(KitError("renv boom")))
    with pytest.raises(KitError, match="renv boom.*rolled back"):
        cmd_add_language("r", p)
    for rel in (".Rprofile", "renv", "renv.lock", "analysis/numbers/make_numbers.R"):
        assert not (p / rel).exists(), rel
    assert load_config(p)["languages"] == ["python"]
    assert sh(p, "rev-parse", "HEAD") == head and sh(p, "status", "--porcelain") == ""


def test_add_package_r_to_python_project_adds_language(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    cmd_add_package("r", p)
    cfg = load_config(p)
    assert cfg["languages"] == ["python", "r"] and cfg["packages"] == {"r": "demo"}
    assert R_PKG_RULE in (p / "CLAUDE.md").read_text()
    assert commits(p) == 2 and sh(p, "status", "--porcelain") == ""


def test_untracked_files_survive_a_failed_run(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "notes" / "scratch.md", "mine\n")
    write(p / "analysis" / "numbers" / "scratch.txt", "mine too\n")
    monkeypatch.setattr(scaffold, "py_install_pkg", lambda project: (_ for _ in ()).throw(KitError("uv boom")))
    with pytest.raises(KitError, match="rolled back"):
        cmd_add_package("python", p)
    assert (p / "notes" / "scratch.md").read_text() == "mine\n"
    assert (p / "analysis" / "numbers" / "scratch.txt").read_text() == "mine too\n"
    assert not (p / "analysis" / "numbers" / "make_numbers.py").exists()


def test_invalid_name_refused_and_nothing_created(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    with pytest.raises(KitError, match="choose another name"):
        cmd_add_package("python", p, "1bad")
    assert not (p / "pkg").exists() and not (p / "pyproject.toml").exists()
    assert sh(p, "status", "--porcelain") == ""


def test_enclosing_repo_refused(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    shutil.rmtree(p / ".git")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(KitError, match="not the top of its own git repository"):
        cmd_add_language("python", p)
    assert not (p / "pyproject.toml").exists()


def test_assume_unchanged_file_refused(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    sh(p, "update-index", "--assume-unchanged", "CLAUDE.md")
    with pytest.raises(KitError, match="assume-unchanged.*CLAUDE.md|CLAUDE.md.*assume-unchanged"):
        cmd_add_language("python", p)
    assert not (p / "pyproject.toml").exists()


def test_ignored_target_path_refused_naming_rule(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    with (p / ".gitignore").open("a") as f:
        f.write(".python-version\n")
    sh(p, "commit", "-qam", "ignore it")
    with pytest.raises(KitError, match=r"\.python-version would be ignored by git \(.*\.gitignore:\d+:\.python-version"):
        cmd_add_language("python", p)
    assert not (p / "pyproject.toml").exists()


def test_failing_slides_gate_refused_up_front(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "slides" / "talk" / "talk.tex",
          "\\documentclass{beamer}\n\\begin{document}\nWe had 3 cases.\n\\end{document}\n")
    sh(p, "add", "-A")
    sh(p, "commit", "-q", "--no-verify", "-m", "talk")
    with pytest.raises(KitError, match="already fails"):
        cmd_add_language("python", p)
    assert not (p / "pyproject.toml").exists()


def test_renv_library_not_ignored_refused_and_rolled_back(tmp_path, monkeypatch):
    p = cmd_new("demo", tmp_path, ["python"])
    head = sh(p, "rev-parse", "HEAD")

    def bad_r_init(project):
        write(project / ".Rprofile", "# stub\n")
        write(project / "renv" / "activate.R", "# stub\n")
        write(project / "renv.lock", "{}\n")
    monkeypatch.setattr(scaffold, "r_init", bad_r_init)
    with pytest.raises(KitError, match="not git-ignored.*rolled back"):
        cmd_add_language("r", p)
    assert not (p / "renv").exists() and sh(p, "rev-parse", "HEAD") == head
    assert sh(p, "status", "--porcelain") == ""


def test_success_output(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    capsys.readouterr()
    cmd_add_package("python", p, "colinf")
    out = capsys.readouterr().out
    assert sh(p, "rev-parse", "--short=7", "HEAD").strip() in out
    assert "(not pushed)" in out and "also added Python to languages" in out
    assert "uv run --locked python" in out
    cmd_add_package("r", tmp_path / "demo")
    out = capsys.readouterr().out
    assert 'renv::install("./pkg/r")' in out and "renv.lock records packages used by any R script" in out


def test_untracked_files_sharing_an_own_name_are_not_committed(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "uv.lock", "experiment\n")
    write(p / "pyproject.toml", "experiment\n")
    cmd_add_package("r", p)
    status = sh(p, "status", "--porcelain")
    assert "?? uv.lock" in status and "?? pyproject.toml" in status
    committed = sh(p, "show", "--name-only", "--format=", "HEAD").split()
    assert "uv.lock" not in committed and "pyproject.toml" not in committed


def test_untracked_renv_lock_not_committed_by_python_add(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    write(p / "renv.lock", "experiment\n")
    cmd_add_package("python", p)
    assert "?? renv.lock" in sh(p, "status", "--porcelain")
    assert "renv.lock" not in sh(p, "show", "--name-only", "--format=", "HEAD").split()


def as_older_project(p):
    """Undo what new projects get from the code spec: the parameter files, the reader, the ignore line and
    the code gate in the hook."""
    for rel in ("analysis/params.yml", "analysis/explore/params.yml", "analysis/params.R"):
        sh(p, "rm", "-q", rel)
    ignore = p / ".gitignore"
    ignore.write_text(ignore.read_text().replace("analysis/explore/out/\n", ""))
    sh(p, "add", ".gitignore")
    sh(p, "commit", "-q", "--no-verify", "-m", "as an older project")
    hook = p / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n# research-kit numbers gate (old)\nexit 0\n")


def test_add_params_fills_in_an_older_project(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    as_older_project(p)
    write(p / "notes" / "draft.md", "uncommitted\n")
    assert cmd_add_params(p) == ["analysis/params.yml", "analysis/explore/params.yml", "analysis/params.R",
                                 ".gitignore"]
    assert "Add the parameter files and readers" in sh(p, "log", "-1", "--format=%s")
    assert sh(p, "status", "--porcelain") == "?? notes/draft.md\n"
    assert "analysis/explore/out/" in (p / ".gitignore").read_text().splitlines()
    assert not (p / "analysis" / "params.py").exists()
    assert "lint_code.py" in (p / ".git" / "hooks" / "pre-commit").read_text()
    assert "the code gate is on" in capsys.readouterr().out
    assert cmd_add_params(p) == [] and "all there" in capsys.readouterr().out
    assert main(["add-params", "--project", str(p)]) == 0


def test_add_params_refuses_a_file_it_did_not_write(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    as_older_project(p)
    write(p / "analysis" / "params.yml", "model:\n  lags: 3\n")
    sh(p, "add", "analysis/params.yml")
    sh(p, "commit", "-q", "--no-verify", "-m", "the project's own params.yml")
    with pytest.raises(KitError, match="analysis/params.yml already exists and is not the kit's"):
        cmd_add_params(p)
    assert not (p / "analysis" / "params.R").exists() and (p / "analysis" / "params.yml").read_text() == \
        "model:\n  lags: 3\n"


def test_add_language_keeps_the_projects_own_reader(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["python"])
    write(p / "analysis" / "params.R", "# our own settings\nlags <- 3\n")
    sh(p, "add", "analysis/params.R")
    sh(p, "commit", "-q", "--no-verify", "-m", "our own params.R")
    cmd_add_language("r", p)
    assert (p / "analysis" / "params.R").read_text() == "# our own settings\nlags <- 3\n"
    assert "kept your own analysis/params.R" in capsys.readouterr().out


def test_add_params_in_a_linked_worktree_leaves_the_hook_alone(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    as_older_project(p)
    wt = tmp_path / "demo-wt"
    sh(p, "worktree", "add", "-q", str(wt), "-b", "params")
    old_hook = (p / ".git" / "hooks" / "pre-commit").read_text()
    assert "analysis/params.yml" in cmd_add_params(wt)
    assert (p / ".git" / "hooks" / "pre-commit").read_text() == old_hook
    assert f"run scaffold.py install-hooks there ({p})" in capsys.readouterr().out


def test_add_params_respects_an_existing_ignore_rule_and_pending_edits(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    as_older_project(p)
    ignore = p / ".gitignore"
    ignore.write_text(ignore.read_text() + "/analysis/explore/out\n")
    sh(p, "commit", "-q", "--no-verify", "-am", "our own way of ignoring it")
    assert ".gitignore" not in cmd_add_params(p)
    assert ignore.read_text().count("explore/out") == 1
    q = cmd_new("demo2", tmp_path, ["r"])
    as_older_project(q)
    (q / ".gitignore").write_text((q / ".gitignore").read_text() + "scratch/\n")     # uncommitted edit
    capsys.readouterr()
    assert ".gitignore" not in cmd_add_params(q)
    assert "add the line analysis/explore/out/ to it yourself" in capsys.readouterr().out
    assert sh(q, "status", "--porcelain", "--", ".gitignore").startswith(" M")


def test_add_params_with_a_shared_hooks_path_still_succeeds(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    as_older_project(p)
    sh(p, "config", "core.hooksPath", str(tmp_path / "shared-hooks"))
    assert main(["add-params", "--project", str(p)]) == 0
    out = capsys.readouterr().out
    assert "add-params: committed" in out and "the code gate is off: " in out and "core.hooksPath" in out
