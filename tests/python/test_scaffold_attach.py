import os
import subprocess

import pytest

from build_fixture import bare_overleaf, set_config
from kitlib import KitError
from scaffold import cmd_attach, cmd_new

MAIN = "\\documentclass{article}\n\\begin{document}\nWe had 3 cases.\n\\end{document}\n"


def git_out(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def test_attach(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    paper = p / "paper"
    for d in ("generated", "figures", "tables"):
        assert (paper / d / ".gitkeep").is_file()
    assert "/*.pdf" in (paper / ".gitignore").read_text()
    assert (paper / ".lint_baseline").read_text() == "1\n"      # measured, not empty
    assert (paper / ".lint_baseline_tables").read_text() == "0\n"
    assert ".lint_baseline_tables" in git_out(paper, "ls-files")
    assert os.access(paper / ".git/hooks/pre-commit", os.X_OK)
    assert "--gate paper" in (paper / ".git/hooks/pre-commit").read_text()
    assert git_out(paper, "rev-list", "--count", "origin/main..HEAD").strip() == "1"  # committed, not pushed
    not_ignored = subprocess.run(["git", "-C", str(paper), "check-ignore", "-q", "figures/x.pdf"])
    assert not_ignored.returncode == 1          # 1 = not ignored: PDF figures are tracked
    ignored = subprocess.run(["git", "-C", str(paper), "check-ignore", "-q", "main.pdf"])
    assert ignored.returncode == 0              # root build PDF is ignored


def test_attach_refuses_existing_paper(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    (p / "paper").mkdir()
    with pytest.raises(KitError, match="already exists"):
        cmd_attach(str(bare), p)


def test_attach_no_matching_files_keeps_clone_and_reruns(tmp_path):
    """The clone needed the user's token: a config mistake must not throw it away."""
    bare = bare_overleaf(tmp_path, {"chapters/other.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    with pytest.raises(KitError, match="kept the clone"):
        cmd_attach(str(bare), p)
    paper = p / "paper"
    assert git_out(paper, "status", "--porcelain", "--ignored").strip() == ""   # untouched
    assert git_out(paper, "rev-list", "--count", "origin/main..HEAD").strip() == "0"
    assert not (paper / ".git/hooks/pre-commit").exists()
    set_config(p, '["*.tex", "sections/**/*.tex"]', '["chapters/*.tex"]')
    cmd_attach(str(bare), p)                                   # the same command, rerun
    assert (paper / ".lint_baseline").read_text() == "1\n"
    assert "--gate paper" in (paper / ".git/hooks/pre-commit").read_text()


def test_attach_failure_after_changes_restores_the_clone(tmp_path, monkeypatch):
    import scaffold

    def broken_hook(*a, **k):
        raise KitError("hook install failed")
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    monkeypatch.setattr(scaffold, "install_hook", broken_hook)
    with pytest.raises(KitError, match="hook install failed.*kept the clone"):
        cmd_attach(str(bare), p)
    paper = p / "paper"
    assert git_out(paper, "status", "--porcelain", "--ignored").strip() == ""
    assert git_out(paper, "rev-list", "--count", "origin/main..HEAD").strip() == "0"   # scaffold commit undone
    monkeypatch.undo()
    cmd_attach(str(bare), p)
    assert (paper / ".lint_baseline").is_file()


def test_attach_failure_between_mkdir_and_commit_restores_the_clone(tmp_path, monkeypatch):
    import lint_numbers

    def broken_lint(*a, **k):
        raise KitError("lint failed")
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN, ".gitignore": "generated/\n"})   # ignores a kit folder
    p = cmd_new("demo", tmp_path, ["r"])
    monkeypatch.setattr(lint_numbers, "lint_text", broken_lint)
    with pytest.raises(KitError, match="lint failed.*kept the clone"):
        cmd_attach(str(bare), p)
    assert git_out(p / "paper", "status", "--porcelain", "--ignored").strip() == ""
    monkeypatch.undo()
    cmd_attach(str(bare), p)


def test_attach_unexpected_error_restores_the_clone_and_propagates(tmp_path, monkeypatch):
    import lint_numbers

    def boom(*a, **k):
        raise ValueError("boom")
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    monkeypatch.setattr(lint_numbers, "lint_text", boom)
    with pytest.raises(ValueError, match="boom"):
        cmd_attach(str(bare), p)
    assert git_out(p / "paper", "status", "--porcelain", "--ignored").strip() == ""


def test_attach_a_project_whose_overleaf_already_has_the_scaffolding(tmp_path, monkeypatch):
    """A paper attached before (scaffold commit pushed) attaches again, and a failed attach reruns."""
    import scaffold
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    first = cmd_new("one", tmp_path, ["r"])
    cmd_attach(str(bare), first)
    subprocess.run(["git", "-C", str(first / "paper"), "push", "-q"], check=True)
    p = cmd_new("two", tmp_path, ["r"])

    def broken_hook(*a, **k):
        raise KitError("hook install failed")
    monkeypatch.setattr(scaffold, "install_hook", broken_hook)
    with pytest.raises(KitError, match="kept the clone"):
        cmd_attach(str(bare), p)
    monkeypatch.undo()
    cmd_attach(str(bare), p)                                   # nothing new to commit, and no refusal
    assert "--gate paper" in (p / "paper/.git/hooks/pre-commit").read_text()


@pytest.mark.parametrize("setup", ["other_remote", "dirty", "scaffolded"])
def test_attach_rerun_refuses_a_clone_it_cannot_reuse(tmp_path, setup):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    paper = p / "paper"
    if setup == "scaffolded":
        cmd_attach(str(bare), p)
    else:
        subprocess.run(["git", "clone", "-q", str(bare), str(paper)], check=True)
        if setup == "other_remote":
            subprocess.run(["git", "-C", str(paper), "remote", "set-url", "origin", str(tmp_path / "x.git")], check=True)
        else:
            (paper / "notes.txt").write_text("mine\n")
    with pytest.raises(KitError, match="already exists"):
        cmd_attach(str(bare), p)
    if setup == "dirty":
        assert (paper / "notes.txt").read_text() == "mine\n"


def test_attach_subfolder_manuscript_puts_folders_beside_generated(tmp_path):
    bare = bare_overleaf(tmp_path, {"draft/main.tex": MAIN, "Tables/t.tex": "x\n"})
    p = cmd_new("demo", tmp_path, ["r"])
    set_config(p, "numbers_tex: paper/generated/numbers.tex", "numbers_tex: paper/draft/generated/numbers.tex")
    set_config(p, "notation_tex: paper/generated/notation.tex", "notation_tex: paper/draft/generated/notation.tex")
    set_config(p, '["*.tex", "sections/**/*.tex"]', '["draft/main.tex"]')
    cmd_attach(str(bare), p)
    paper = p / "paper"
    for d in ("generated", "figures", "tables"):
        assert (paper / "draft" / d / ".gitkeep").is_file()
        assert not (paper / d).exists()
    assert (paper / "Tables/t.tex").is_file()                 # the project's own folders are left alone


def test_attach_refuses_generated_outside_the_paper(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    set_config(p, "numbers_tex: paper/generated/numbers.tex", "numbers_tex: generated/numbers.tex")
    with pytest.raises(KitError, match="numbers_tex.*inside paper_dir"):
        cmd_attach(str(bare), p)


def test_attach_records_actual_branch(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN}, branch="master")   # non-default branch
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    assert "paper_branch: master" in (p / ".claude/research.yml").read_text()


def test_template_default_branch_matches_overleaf(tmp_path):
    """Overleaf git integration serves `main`; attaching must not need to rewrite research.yml."""
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})                     # Overleaf-like: main
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    assert git_out(p, "status", "--porcelain").strip() == ""


def test_default_globs_cover_root_and_nested_sections(tmp_path):
    from build_fixture import write
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN.replace("We had 3 cases.", "Hello.")})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    paper = p / "paper"
    write(paper / "intro.tex", "Power is 0.81.\n")
    write(paper / "sections" / "sub" / "a.tex", "Bias is 0.02.\n")
    write(paper / "tables" / "t1.tex", "0.94 & 0.95 \\\\\n")      # generated tables stay unlinted
    subprocess.run(["git", "-C", str(paper), "add", "-A"], check=True)
    r = subprocess.run(["git", "-C", str(paper), "commit", "-m", "x"], capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "intro.tex" in out and "sections/sub/a.tex" in out and "t1.tex" not in out


def test_attach_measures_the_table_baseline(tmp_path):
    table = ("\\begin{table}\\begin{tabular}{lc}\na & -0.5 \\\\\nb & -1 \\\\\n\\end{tabular}\\end{table}\n")
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN.replace("We had 3 cases.", "\\input{tables/t}"),
                                    "tables/t.tex": table})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "2\n"
