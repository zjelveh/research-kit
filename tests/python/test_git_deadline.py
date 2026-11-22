import os
import time

import pytest

import codex_review
import lint_numbers
from build_fixture import init_repo, write
from kitlib import GitTimeout, git, git_deadline, time_left


def slow_git_on_path(tmp_path, monkeypatch):
    """A `git` first on PATH that hangs. `exec`, so the process the timeout kills is the sleeper itself."""
    fake = write(tmp_path / "bin" / "git", "#!/bin/sh\nexec sleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")


def test_a_used_up_budget_skips_git_calls(tmp_path):
    r = init_repo(tmp_path / "r")
    with git_deadline(0) as budget:
        with pytest.raises(GitTimeout, match="time limit"):
            git(r, "status")
    assert budget.timed_out
    assert "nothing to commit" in git(r, "status")


def test_a_slow_git_is_stopped_at_the_deadline(tmp_path, monkeypatch):
    r = init_repo(tmp_path / "r")
    slow_git_on_path(tmp_path, monkeypatch)
    start = time.monotonic()
    with git_deadline(1) as budget:
        with pytest.raises(GitTimeout, match="git status in .* stopped: session start's 1s for git checks ran out"):
            git(r, "status")
    assert time.monotonic() - start < 5 and budget.timed_out


def test_a_calls_own_shorter_timeout_leaves_the_record_alone(tmp_path, monkeypatch):
    """Like fetch's 5 seconds: when its own limit, not the budget, stops a call, nothing later is skipped."""
    r = init_repo(tmp_path / "r")
    slow_git_on_path(tmp_path, monkeypatch)
    with git_deadline(60) as budget:
        with pytest.raises(GitTimeout, match="timed out after 1s"):
            git(r, "fetch", timeout=1)
        assert time_left() > 50
    assert not budget.timed_out


def test_without_a_deadline_timeouts_are_unchanged():
    assert time_left(None) is None and time_left(3) == 3


def test_a_deadline_caps_each_timeout():
    with git_deadline(60):
        assert time_left(5) == 5 and 55 < time_left() <= 60


def test_an_inner_deadline_restores_the_outer_one(tmp_path):
    r = init_repo(tmp_path / "r")
    with git_deadline(60) as outer:
        with git_deadline(0) as inner:
            with pytest.raises(GitTimeout):
                git(r, "status")
        assert 55 < time_left() <= 60
        git(r, "status")
    assert inner.timed_out and not outer.timed_out
    assert time_left() is None


def test_an_inner_deadline_cannot_outlast_the_outer_one(tmp_path):
    r = init_repo(tmp_path / "r")
    with git_deadline(5):
        with git_deadline(60):
            assert time_left() <= 5
    with git_deadline(0) as outer:
        with git_deadline(60) as inner:
            with pytest.raises(GitTimeout, match="time limit"):
                git(r, "status")
    assert inner.timed_out and outer.timed_out


def test_a_call_stopped_by_the_outer_deadline_names_its_budget(tmp_path, monkeypatch):
    r = init_repo(tmp_path / "r")
    slow_git_on_path(tmp_path, monkeypatch)
    with git_deadline(1) as outer:
        with git_deadline(60) as inner:
            with pytest.raises(GitTimeout, match="stopped: session start's 1s for git checks ran out"):
                git(r, "status")
    assert inner.timed_out and outer.timed_out


def test_the_deadline_ends_with_an_exception():
    with pytest.raises(RuntimeError):
        with git_deadline(0):
            raise RuntimeError("boom")
    assert time_left(3) == 3


def symlinked(tmp_path):
    r = tmp_path / "r"
    write(r / "target.R", "x <- 1\n")
    (r / "link.R").symlink_to("target.R")
    return init_repo(r)


@pytest.mark.parametrize("call", [
    lambda r: codex_review.worktree_blob(r, "link.R"),
    lambda r: codex_review.worktree_blob(r, "target.R"),
    lambda r: lint_numbers._show(r, "HEAD:target.R"),
], ids=["worktree_blob-symlink", "worktree_blob-file", "lint-show"])
def test_other_git_calls_keep_the_deadline(tmp_path, call):
    r = symlinked(tmp_path)
    with git_deadline(0) as budget:
        with pytest.raises(GitTimeout, match="time limit"):
            call(r)
    assert budget.timed_out


@pytest.mark.parametrize("call", [
    lambda r: codex_review.worktree_blob(r, "link.R"),
    lambda r: lint_numbers._show(r, "HEAD:target.R"),
], ids=["worktree_blob-symlink", "lint-show"])
def test_direct_git_calls_are_stopped_at_the_deadline(tmp_path, monkeypatch, call):
    """These two run git without git(): a slow git still ends at the deadline and marks the record."""
    r = symlinked(tmp_path)
    slow_git_on_path(tmp_path, monkeypatch)
    start = time.monotonic()
    with git_deadline(1) as budget:
        with pytest.raises(GitTimeout, match="stopped: session start's 1s for git checks ran out"):
            call(r)
    assert time.monotonic() - start < 5 and budget.timed_out
