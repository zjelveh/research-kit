import datetime as dt
import os
import shutil
import subprocess

import pytest

from build_fixture import git, write
from codex_review import (REF_NS, ReviewExit, housekeeping, make_copy, new_folder, pathspec, prune_refs,
                          remove_copy, snapshot)
from review_fixture import code_project, head


def state(p):
    return (git(p, "status", "--porcelain", "-uall"), head(p), (p / ".git" / "index").read_bytes())


def test_clean_tree_is_reviewed_at_head(tmp_path):
    p = code_project(tmp_path)
    assert snapshot(p, "r1") == (head(p), False)
    assert git(p, "for-each-ref", REF_NS) == ""


def test_the_reviews_folder_is_never_uncommitted_work(tmp_path):
    p = code_project(tmp_path)
    write(p / "notes" / "reviews" / "r0" / "author_brief.md", "claims\n")
    assert snapshot(p, "r1", exclude=p / "notes" / "reviews") == (head(p), False)
    write(p / "analysis" / "a.R", "x <- 99\n")
    reviewed, dirty = snapshot(p, "r1", exclude=p / "notes" / "reviews")
    assert dirty and "notes/reviews/r0/author_brief.md" not in git(p, "ls-tree", "-r", "--name-only", reviewed)


def test_pathspec_leaves_out_the_reviews_folder_only_inside_the_project(tmp_path):
    p = code_project(tmp_path)
    (p / "data" / "reviews").mkdir(parents=True)
    assert pathspec(p, p / "..reviews") == ["--", ".", ":(exclude)..reviews"]   # a folder, not the parent
    assert pathspec(p, p / ".." / "elsewhere") == ["--", "."]
    assert pathspec(p, p / "data" / "reviews") == ["--", "."]                   # gitignored: git refuses it
    write(p / "..reviews" / "r0" / "author_brief.md", "claims\n")
    assert snapshot(p, "r1", exclude=p / "..reviews") == (head(p), False)


def test_snapshot_of_uncommitted_work_leaves_the_project_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path))
    p = code_project(tmp_path)
    write(p / "analysis" / "a.R", "x <- 99\n")
    write(p / "analysis" / "staged.py", "s = 1\n")
    git(p, "add", "analysis/staged.py")
    write(p / "analysis" / "new.py", "z = 1\n")
    write(p / "data" / "secret.R", "ignored\n")
    before = state(p)
    reviewed, dirty = snapshot(p, "r1")
    assert dirty and state(p) == before
    assert git(p, "rev-parse", REF_NS + "r1").strip() == reviewed
    assert git(p, "rev-parse", f"{reviewed}^").strip() == head(p)
    files = set(git(p, "ls-tree", "-r", "--name-only", reviewed).split())
    assert {"analysis/a.R", "analysis/staged.py", "analysis/new.py"} <= files
    assert "data/secret.R" not in files
    assert git(p, "show", f"{reviewed}:analysis/a.R") == "x <- 99\n"


def test_snapshot_never_overwrites_an_existing_ref(tmp_path, monkeypatch):
    """Two worktrees can pick the same folder name at once; the second must not take the first's ref."""
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path))
    p = code_project(tmp_path)
    theirs = git(p, "rev-parse", "HEAD~1").strip()
    git(p, "update-ref", REF_NS + "r1", theirs)
    write(p / "analysis" / "a.R", "x <- 99\n")
    with pytest.raises(ReviewExit) as e:
        snapshot(p, "r1")
    assert e.value.code == 2 and REF_NS + "r1" in str(e.value)
    assert git(p, "rev-parse", REF_NS + "r1").strip() == theirs


def test_prune_refs_keeps_only_the_named_one(tmp_path):
    p = code_project(tmp_path)
    out = p / "notes" / "reviews"
    for name in ("r1", "r2", "r3"):
        git(p, "update-ref", REF_NS + name, head(p))
        (out / name).mkdir(parents=True)
    prune_refs(p, out, "r2")
    assert git(p, "for-each-ref", "--format=%(refname)", REF_NS).split() == [REF_NS + "r2"]
    prune_refs(p, out, None)
    assert git(p, "for-each-ref", REF_NS) == ""


def test_prune_refs_leaves_other_worktrees_refs(tmp_path):
    """refs/kit-reviews/ is shared by every worktree of a repo; each prunes only its own reviews."""
    p = code_project(tmp_path)
    out = p / "notes" / "reviews"
    for name in ("mine-1", "mine-2", "theirs"):
        git(p, "update-ref", REF_NS + name, head(p))
    (out / "mine-1").mkdir(parents=True)
    (out / "mine-2").mkdir()
    prune_refs(p, out, "mine-2")
    assert git(p, "for-each-ref", "--format=%(refname)", REF_NS).split() == [REF_NS + "mine-2", REF_NS + "theirs"]
    prune_refs(p, out, None)
    assert git(p, "for-each-ref", "--format=%(refname)", REF_NS).split() == [REF_NS + "theirs"]


def test_new_folder_skips_a_name_whose_ref_exists(tmp_path):
    """Another worktree's same-minute review of the same head would otherwise overwrite its ref."""
    p = code_project(tmp_path)
    git(p, "update-ref", REF_NS + "2026-10-21T0905-codex-abcdef1", head(p))
    now = dt.datetime(2026, 10, 21, 9, 5)
    assert new_folder(p / "notes" / "reviews", "abcdef1234", now=now, project=p).name == "2026-10-21T0905-codex-abcdef1-2"


def test_copy_has_the_reviewed_files_and_environment_links(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    p = code_project(tmp_path)
    write(p / "renv" / "library" / "marker", "lib\n")
    (p / ".venv").mkdir()
    write(p / ".gitignore", "data/\nrenv/library/\n.venv/\n")
    git(p, "add", ".gitignore")
    git(p, "commit", "-q", "-m", "ignore envs")
    (p / "analysis" / "b.py").unlink()
    write(p / "fig.bin", "")
    (p / "fig.bin").write_bytes(bytes(range(256)))
    reviewed, _ = snapshot(p, "r1")
    tmp = make_copy(p, reviewed)
    copy = tmp / "copy"
    assert (tmp / "pid").read_text().strip() == str(os.getpid())
    assert (copy / "analysis" / "a.R").is_file() and not (copy / "analysis" / "b.py").exists()
    assert (copy / "fig.bin").read_bytes() == bytes(range(256))
    assert (copy / "renv" / "library").is_symlink() and (copy / "renv" / "library" / "marker").is_file()
    assert (copy / ".venv").is_symlink() and (copy / ".tmp").is_dir()
    remove_copy(p, tmp)
    assert not tmp.exists()
    assert (p / "renv" / "library" / "marker").is_file() and (p / ".venv").is_dir()   # targets survive
    assert git(p, "worktree", "list").count("\n") == 1


def test_housekeeping_removes_only_dead_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmp"))
    p = code_project(tmp_path)
    dead = subprocess.Popen(["true"])
    dead.wait()
    for name, pid in (("kit-review-dead", dead.pid), ("kit-review-live", os.getpid())):
        d = tmp_path / "tmp" / name
        d.mkdir(parents=True)
        (d / "pid").write_text(f"{pid}\n")
    fresh = tmp_path / "tmp" / "kit-review-fresh"      # no pid file yet, just created
    fresh.mkdir()
    housekeeping(p)
    assert not (tmp_path / "tmp" / "kit-review-dead").exists()
    assert (tmp_path / "tmp" / "kit-review-live").exists() and fresh.exists()


def test_housekeeping_unregisters_only_stale_kit_copies(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    p = code_project(tmp_path)
    gone, dead, live = (make_copy(p, head(p)) for _ in range(3))
    git(p, "worktree", "lock", "--reason", "initializing", str(gone / "copy"))   # as a killed `worktree add` leaves it
    shutil.rmtree(gone)
    done = subprocess.Popen(["true"])
    done.wait()
    (dead / "pid").write_text(f"{done.pid}\n")
    housekeeping(p)
    listed = git(p, "worktree", "list", "--porcelain")
    assert str(gone) not in listed and str(dead) not in listed and not dead.exists()
    assert f"worktree {live / 'copy'}\n" in listed and (live / "copy" / "analysis" / "a.R").is_file()
    remove_copy(p, live)
    assert git(p, "worktree", "list").count("\n") == 1 and not live.exists()


def test_housekeeping_unregisters_stale_kit_copies_under_another_temp_root(tmp_path, monkeypatch):
    """A copy made while the temp root was another folder (another session's TMPDIR) is still the kit's."""
    for root in ("tmpA", "tmpB"):
        (tmp_path / root).mkdir()
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmpA"))
    p = code_project(tmp_path)
    gone, dead, live = (make_copy(p, head(p)) for _ in range(3))
    shutil.rmtree(gone)
    done = subprocess.Popen(["true"])
    done.wait()
    (dead / "pid").write_text(f"{done.pid}\n")
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmpB"))
    housekeeping(p)
    listed = git(p, "worktree", "list", "--porcelain")
    assert str(gone) not in listed and str(dead) not in listed
    assert f"worktree {live / 'copy'}\n" in listed and (live / "copy" / "analysis" / "a.R").is_file()
    remove_copy(p, live)


def test_new_folder_names_and_same_minute_retries(tmp_path):
    out = tmp_path / "reviews"
    now = dt.datetime(2026, 10, 21, 9, 5)
    a = new_folder(out, "abcdef1234", now=now)
    b = new_folder(out, "abcdef1234", now=now)
    assert a.name == "2026-10-21T0905-codex-abcdef1" and b.name == "2026-10-21T0905-codex-abcdef1-2"
    assert new_folder(out, "abcdef1234", reviewer="claude", now=now).name == "2026-10-21T0905-claude-abcdef1"
