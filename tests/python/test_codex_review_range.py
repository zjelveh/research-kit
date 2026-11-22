import os
import time

import pytest

import codex_review
from build_fixture import git, write
from codex_review import (ReviewExit, changed_code_files, empty_tree, is_code, last_complete,
                          range_start, review_status, reviews, snapshot)
from review_fixture import code_project, fake_review, head


def test_code_extensions():
    assert all(is_code(p) for p in ["a.R", "b.r", "c.Rmd", "d.qmd", "e.py", "f.sh", "g.sql", "h.stan", "i.jl", "j.do"])
    assert not any(is_code(p) for p in ["memo.md", "data.csv", "fig.png", "Makefile"])


def test_first_review_starts_twenty_commits_back_or_at_the_start(tmp_path):
    p = code_project(tmp_path, commits=3)
    start, how = range_start(p, p / "notes" / "reviews", None)
    assert start == empty_tree(p) and how == "the start of the history"
    for k in range(20):
        git(p, "commit", "-q", "--allow-empty", "-m", f"e{k}")
    start, how = range_start(p, p / "notes" / "reviews", None)
    assert start == git(p, "rev-parse", "HEAD~20").strip() and how == "20 commits back"


def test_base_given_and_bad_base(tmp_path):
    p = code_project(tmp_path)
    first = git(p, "rev-list", "--max-parents=0", "HEAD").strip()
    assert range_start(p, p / "notes" / "reviews", first)[0] == first
    with pytest.raises(ReviewExit) as e:
        range_start(p, p / "notes" / "reviews", "no-such-ref")
    assert e.value.code == 2


def test_newest_complete_codex_review_is_the_start(tmp_path):
    p = code_project(tmp_path)
    older = git(p, "rev-parse", "HEAD~1").strip()
    fake_review(p, "a", older, finished="2026-10-18T09:00:00")
    fake_review(p, "b", head(p), finished="2026-10-18T10:00:00")
    fake_review(p, "c", older, status="incomplete", finished="2026-10-18T11:00:00")
    fake_review(p, "d", older, reviewer="claude", finished="2026-10-18T12:00:00")
    assert last_complete(p / "notes" / "reviews")["_folder"] == "b"
    assert range_start(p, p / "notes" / "reviews", None)[0] == head(p)


def test_unreachable_review_state_falls_back(tmp_path, capsys):
    p = code_project(tmp_path)
    fake_review(p, "a", "0" * 40)
    assert range_start(p, p / "notes" / "reviews", None)[0] == empty_tree(p)
    assert "unreachable" in capsys.readouterr().err


def test_changed_code_files_tracked_untracked_and_deleted(tmp_path):
    p = code_project(tmp_path)
    start = head(p)
    assert changed_code_files(p, start) == []
    write(p / "analysis" / "a.R", "x <- 99\n")                 # modified
    write(p / "analysis" / "new.py", "z = 1\n")                # untracked
    write(p / "notes" / "memo.md", "changed\n")                # not code
    write(p / "data" / "big.R", "ignored\n")                   # ignored
    (p / "analysis" / "b.py").unlink()                         # deleted
    assert changed_code_files(p, start) == ["analysis/a.R", "analysis/b.py", "analysis/new.py"]


def test_untracked_file_in_the_reviewed_state_compares_by_content(tmp_path):
    """A file untracked at review time and still untracked counts only if its content changed."""
    p = code_project(tmp_path)
    write(p / "analysis" / "new.py", "z = 1\n")
    git(p, "add", "analysis/new.py")
    git(p, "commit", "-q", "-m", "snap")
    snap = head(p)                                             # stands in for a review snapshot
    git(p, "reset", "-q", "--mixed", "HEAD~1")                 # new.py untracked again, same content
    assert changed_code_files(p, snap) == []
    write(p / "analysis" / "new.py", "z = 2\n")
    assert changed_code_files(p, snap) == ["analysis/new.py"]


def test_untracked_symlinked_code_file_compares_by_its_link_text(tmp_path):
    """`git add -A` stores a symlink's text, so that is what an untracked link is compared by."""
    p = code_project(tmp_path)
    write(tmp_path / "shared" / "h.R", "h <- 1\n")
    (p / "analysis" / "h.R").symlink_to(tmp_path / "shared" / "h.R")
    git(p, "add", "analysis/h.R")
    git(p, "commit", "-q", "-m", "snap")
    snap = head(p)                                             # stands in for a review snapshot
    git(p, "reset", "-q", "--mixed", "HEAD~1")                 # the link is untracked again
    assert changed_code_files(p, snap) == []
    write(tmp_path / "shared" / "h.R", "h <- 2\n")             # the target's content is not the link's
    assert changed_code_files(p, snap) == []
    (p / "analysis" / "h.R").unlink()
    (p / "analysis" / "h.R").symlink_to(tmp_path / "shared" / "other.R")
    assert changed_code_files(p, snap) == ["analysis/h.R"]     # dangling, and pointing elsewhere


def test_dangling_or_vanished_untracked_code_files_count_as_changed(tmp_path, monkeypatch):
    p = code_project(tmp_path)
    write(tmp_path / "shared" / "gone.R", "g <- 1\n")
    (p / "analysis" / "gone.R").symlink_to(tmp_path / "shared" / "gone.R")
    write(p / "analysis" / "brief.py", "b = 1\n")
    git(p, "add", "analysis")
    git(p, "commit", "-q", "-m", "snap")
    snap = head(p)                                             # both reviewed while untracked
    git(p, "reset", "-q", "--mixed", "HEAD~1")
    (tmp_path / "shared" / "gone.R").unlink()                  # the link's target goes away
    assert changed_code_files(p, snap) == []                   # the link itself is unchanged
    (p / "analysis" / "gone.R").unlink()
    (p / "analysis" / "gone.R").symlink_to(tmp_path / "nowhere.R")
    assert changed_code_files(p, snap) == ["analysis/gone.R"]
    fake_review(p, "r", snap)
    assert review_status(p) == "review: 1 code file changed since the last review (2026-10-18)"
    real_git = codex_review.git

    def vanishing_git(repo, *args, **kw):                      # deleted between ls-files and hashing
        if args[:1] == ("hash-object",):
            (p / "analysis" / "brief.py").unlink(missing_ok=True)
        return real_git(repo, *args, **kw)
    monkeypatch.setattr(codex_review, "git", vanishing_git)
    assert changed_code_files(p, snap) == ["analysis/brief.py", "analysis/gone.R"]


def test_code_files_in_the_reviews_folder_are_not_counted(tmp_path):
    p = code_project(tmp_path)
    fake_review(p, "0-old", head(p))
    write(p / "notes" / "reviews" / "0-old" / "repro.py", "print(1)\n")
    assert changed_code_files(p, head(p), p / "notes" / "reviews") == []
    assert review_status(p) is None
    write(p / "docs" / "reviews" / "r" / "repro.R", "1\n")
    assert changed_code_files(p, head(p), p / "docs" / "reviews") == ["notes/reviews/0-old/repro.py"]


def test_status_line_writes_nothing_to_the_repo(tmp_path, monkeypatch):
    """git status and git diff refresh the index of a touched but unchanged file unless told not to."""
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path))
    p = code_project(tmp_path)
    fake_review(p, "0-old", head(p))
    write(p / "analysis" / "new.py", "z = 1\n")                # untracked, so the snapshot has work
    old = time.time() - 3600
    os.utime(p / "analysis" / "b.py", (old, old))              # touched, content unchanged
    index = p / ".git" / "index"
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    assert review_status(p) == "review: 1 code file changed since the last review (2026-10-18)"
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before
    snapshot(p, "r1", exclude=p / "notes" / "reviews")
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before


def test_a_same_second_edit_is_seen_through_the_index_copy(tmp_path, monkeypatch):
    """git content-checks an entry whose mtime is not older than the index file ("racily clean"). An
    index copy with a fresh mtime would trust the stale stat data and miss a same-size edit."""
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path))
    p = code_project(tmp_path)
    git(p, "config", "core.trustctime", "false")              # only the mtime race, not ctime
    a, index = p / "analysis" / "a.R", p / ".git" / "index"
    past = time.time_ns() - 100 * 10**9
    os.utime(a, ns=(past, past))
    git(p, "add", "analysis/a.R")                              # the index records a.R's stat
    fake_review(p, "0-old", head(p))
    a.write_text("x <- 7\n")                                  # same size as the committed "x <- 3"
    os.utime(a, ns=(past, past))                               # the stat the index recorded
    os.utime(index, ns=(past, past))                           # as if both were written in one second
    assert review_status(p) == "review: 1 code file changed since the last review (2026-10-18)"
    write(p / "analysis" / "new.py", "z = 1\n")                # other work, so a snapshot is made
    reviewed, dirty = snapshot(p, "r1", exclude=p / "notes" / "reviews")
    assert dirty and git(p, "show", f"{reviewed}:analysis/a.R") == "x <- 7\n"


def test_status_line(tmp_path):
    p = code_project(tmp_path)
    assert review_status(p) == "review: none yet (2 code files changed in the last 20 commits)"
    fake_review(p, "a", head(p), finished="2026-10-18T10:00:00")
    assert review_status(p) is None
    write(p / "analysis" / "a.R", "x <- 99\n")
    assert review_status(p) == "review: 1 code file changed since the last review (2026-10-18)"


def test_malformed_review_records_are_skipped(tmp_path):
    """A hand-edited meta.json must not break the status line, which session start shows every time."""
    p = code_project(tmp_path)
    fake_review(p, "a", git(p, "rev-parse", "HEAD~1").strip(), finished="2026-10-18T10:00:00")
    fake_review(p, "b", head(p), finished=20261019)                         # not a string
    fake_review(p, "c", ["not", "a", "commit"], finished="2026-10-20T10:00:00")
    broken = p / "notes" / "reviews" / "d"
    broken.mkdir()
    (broken / "meta.json").write_bytes(b'{"reviewer": "codex", "status": "complete", "x": "\xff"}')
    assert [r["_folder"] for r in reviews(p / "notes" / "reviews")] == ["a"]
    assert review_status(p) == "review: 1 code file changed since the last review (2026-10-18)"


def test_status_line_without_commits(tmp_path):
    p = tmp_path / "empty"
    p.mkdir()
    git(p, "init", "-q")
    assert review_status(p) is None
