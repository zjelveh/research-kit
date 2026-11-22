import json
import os
import shlex
import shutil
import time

import codex_review

from build_fixture import git, init_repo, write
from codex_review import REF_NS, main, review_status, validate
from kitlib import KitError
from review_fixture import assert_stopped, code_project, fake_review, head, install_fake_codex


def run(p, *extra):
    return main(["--project", str(p), *extra])


def only_folder(p):
    folders = sorted((p / "notes" / "reviews").iterdir())
    assert len(folders) == 1, folders
    return folders[0]


def test_complete_review_writes_every_record(tmp_path, monkeypatch):
    record = install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    brief = write(tmp_path / "author.md", "Claims: a.R sets x to 3.\nWeak spots: none.\n")
    assert run(p, "--brief", str(brief)) == 0
    folder = only_folder(p)
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["status"] == "complete" and meta["reviewer"] == "codex" and meta["dirty"] is False
    assert meta["reviewed"] == head(p) and meta["changed_files"] == ["analysis/a.R", "analysis/b.py"]
    assert (folder / "author_brief.md").read_text() == brief.read_text()
    assert "Claims: a.R sets x to 3." in (folder / "brief.md").read_text()
    assert "### F1 (high, code bug): `analysis/a.R:3`" in (folder / "report.md").read_text()
    assert json.loads((folder / "findings.json").read_text())["findings"][0]["id"] == "F1"
    rec = json.loads(record.read_text())
    argv = rec["argv"]
    assert argv[:2] == ["exec", "-C"] and "workspace-write" in argv and argv[-1] == "-"
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in argv
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in argv
    assert rec["tmpdir"].endswith("/copy/.tmp")
    assert meta["command"].startswith(shlex.quote(str(tmp_path / "bin" / "codex")) + " exec -C ")
    assert str(p.resolve()) in rec["brief"] and "analysis/b.py" in rec["brief"]
    assert "pkgload::load_all" in rec["brief"]
    assert not list((tmp_path / "tmp").glob("kit-review-*"))          # copy removed
    assert git(p, "for-each-ref", REF_NS) == ""                       # a clean tree needs no snapshot
    assert review_status(p) is None


def test_a_failed_runs_folder_does_not_make_the_next_review_dirty(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch, mode="nologin")
    p = code_project(tmp_path)
    brief = write(tmp_path / "author.md", "Claims: none.\n")
    assert run(p, "--brief", str(brief)) == 3
    monkeypatch.setenv("FAKE_CODEX_MODE", "ok")
    assert run(p, "--brief", str(brief)) == 0
    newest = max((p / "notes" / "reviews").glob("*/meta.json"), key=lambda m: json.loads(m.read_text())["finished"])
    assert json.loads(newest.read_text())["dirty"] is False
    assert git(p, "for-each-ref", REF_NS) == ""


def test_uncommitted_work_reviewed_then_committed_counts_as_reviewed(tmp_path, monkeypatch):
    record = install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    fake_review(p, "0-old", head(p))
    git(p, "update-ref", REF_NS + "0-old", head(p))     # an older snapshot ref, to be pruned
    write(p / "analysis" / "a.R", "x <- 99\n")
    write(p / "analysis" / "new.py", "z = 1\n")

    def outside_reviews():
        return [l for l in git(p, "status", "--porcelain", "-uall").splitlines() if "notes/reviews/" not in l]
    before = outside_reviews()
    assert run(p) == 0
    assert outside_reviews() == before                  # only the review folder is new
    rec = json.loads(record.read_text())
    assert "analysis/new.py" in rec["files"]
    meta = json.loads((sorted((p / "notes" / "reviews").glob("*-codex-*"))[-1] / "meta.json").read_text())
    assert meta["dirty"] is True and meta["changed_files"] == ["analysis/a.R", "analysis/new.py"]
    assert git(p, "for-each-ref", "--format=%(refname)", REF_NS).split() == [REF_NS + meta["folder"]]
    assert review_status(p) is None
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "commit the reviewed work unchanged")
    assert review_status(p) is None
    assert run(p) == 0                                  # nothing to review
    write(p / "analysis" / "a.R", "x <- 100\n")
    assert review_status(p).startswith("review: 1 code file changed since the last review")


def test_background_processes_codex_leaves_are_stopped(tmp_path, monkeypatch):
    """They would outlive the review, in a copy deleted under them."""
    record = install_fake_codex(tmp_path, monkeypatch, mode="background")
    p = code_project(tmp_path)
    assert run(p) == 0
    assert_stopped(json.loads(record.read_text())["child"])


def test_a_gitignored_reviews_folder_does_not_break_a_dirty_review(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    write(p / ".gitignore", "data/\nnotes/\n")
    git(p, "commit", "-qam", "ignore notes")
    brief = write(tmp_path / "author.md", "Claims: none.\n")
    for k, out in enumerate(("notes/reviews", "data/reviews")):        # ignored by notes/, and by data/
        write(p / "analysis" / "a.R", f"x <- {100 + k}\n")
        assert run(p, "--brief", str(brief), "--out", out) == 0, out
        meta = json.loads(next((p / out).glob("*/meta.json")).read_text())
        assert meta["status"] == "complete" and meta["dirty"] is True
        tree = git(p, "ls-tree", "-r", "--name-only", meta["reviewed"])
        assert "analysis/a.R" in tree and out not in tree
        assert git(p, "show", f"{meta['reviewed']}:analysis/a.R") == f"x <- {100 + k}\n"


def test_a_users_worktree_whose_folder_is_missing_survives_a_review(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    wt = tmp_path / "drive" / "feature"
    git(p, "worktree", "add", "-q", "-b", "feature", str(wt))
    wt.rename(tmp_path / "away")                       # an unmounted drive, or a folder moved for a moment
    write(p / "analysis" / "a.R", "x <- 99\n")
    assert run(p) == 0
    (tmp_path / "away").rename(wt)
    assert f"worktree {wt}\n" in git(p, "worktree", "list", "--porcelain")
    assert (p / ".git" / "worktrees" / "feature" / "index").is_file()
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feature"


def test_nothing_to_review_creates_no_folder(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    fake_review(p, "0-old", head(p))
    assert run(p) == 0
    assert "nothing to review" in capsys.readouterr().out
    assert [f.name for f in (p / "notes" / "reviews").iterdir()] == ["0-old"]


def test_codex_missing_or_signed_out_is_exit_3_with_the_brief_kept(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch, mode="nologin")
    p = code_project(tmp_path)
    assert run(p) == 3
    folder = only_folder(p)
    assert (folder / "brief.md").is_file()
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["status"] == "error" and "codex is not signed in" in meta["notes"][0]
    # no codex at all: PATH holds only git, so the real codex on this machine can never be reached
    gitonly = tmp_path / "gitonly"
    gitonly.mkdir()
    (gitonly / "git").symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", str(gitonly))
    assert run(p) == 3


def test_the_codex_checked_is_the_codex_run(tmp_path, monkeypatch, capsys):
    """With a bare name, exec tries every PATH entry: a fake that can't run would hand over to a later
    codex (the real one). A harmless stand-in plays that later codex here."""
    later = tmp_path / "later"
    later.mkdir()
    ran = tmp_path / "later-codex-ran"
    write(later / "codex", f"#!/bin/sh\ntouch '{ran}'\n").chmod(0o755)
    monkeypatch.setenv("PATH", f"{later}{os.pathsep}{os.environ['PATH']}")
    install_fake_codex(tmp_path, monkeypatch)
    assert str(later) not in os.environ["PATH"].split(os.pathsep)      # the fixture drops other codexes
    (tmp_path / "bin" / "codex").write_text("#!/nonexistent/python3\n")  # the fake can't run (noexec, bad shebang)
    monkeypatch.setenv("PATH", f"{os.environ['PATH']}{os.pathsep}{later}")
    p = code_project(tmp_path)
    assert run(p) == 3
    assert not ran.exists()
    assert "could not be run" in capsys.readouterr().err
    assert "could not be run" in json.loads((only_folder(p) / "meta.json").read_text())["notes"][0]


def test_a_codex_check_that_hangs_is_exit_3(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch, mode="hang")
    monkeypatch.setattr(codex_review, "CHECK_TIMEOUT", 1)
    p = code_project(tmp_path)
    t0 = time.monotonic()
    assert run(p) == 3
    assert time.monotonic() - t0 < 20
    meta = json.loads((only_folder(p) / "meta.json").read_text())
    assert "login status did not answer within 1 s" in meta["notes"][0]


def test_codex_unavailable_keeps_the_snapshot_for_a_fallback_review(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch, mode="nologin")
    p = code_project(tmp_path)
    write(p / "analysis" / "a.R", "x <- 99\n")
    assert run(p) == 3
    meta = json.loads((only_folder(p) / "meta.json").read_text())
    assert meta["dirty"] is True
    assert git(p, "for-each-ref", "--format=%(refname)", REF_NS).split() == [REF_NS + meta["folder"]]


def test_codex_failure_and_bad_findings_are_exit_5(tmp_path, monkeypatch):
    for mode in ("fail", "invalid", "badschema"):
        root = tmp_path / mode
        root.mkdir()
        install_fake_codex(root, monkeypatch, mode=mode)
        p = code_project(root)
        write(p / "analysis" / "a.R", "x <- 99\n")            # dirty, so a snapshot ref is made and must go
        assert run(p) == 5, mode
        meta = json.loads((only_folder(p) / "meta.json").read_text())
        assert meta["status"] == "error" and meta["stderr_tail"] is not None and meta["dirty"] is True
        assert meta["notes"][0].startswith({"fail": "codex exited 1", "invalid": "Codex's answer is missing",
                                            "badschema": "Codex's answer does not match"}[mode])
        assert git(p, "for-each-ref", REF_NS) == ""
        assert not list((root / "tmp").glob("kit-review-*"))          # copy removed on errors too


def test_a_sandbox_wider_than_the_copy_stops_codex_at_once(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "workspace-write [workdir, /tmp, $TMPDIR]")
    monkeypatch.setenv("FAKE_CODEX_DELAY", "30")
    done = tmp_path / "done"
    monkeypatch.setenv("FAKE_CODEX_DONE", str(done))
    p = code_project(tmp_path)
    write(p / "analysis" / "b.py", "y = 1\n")                        # uncommitted: a snapshot ref is made
    t0 = time.monotonic()
    assert run(p) == 5
    assert time.monotonic() - t0 < 5 and not done.exists()           # stopped before it did anything
    err = capsys.readouterr().err
    assert "workspace-write [workdir, /tmp, $TMPDIR]" in err and "KNOWN-ISSUES.md" in err
    meta = json.loads((only_folder(p) / "meta.json").read_text())
    assert meta["status"] == "error" and "sandbox" in meta["notes"][0]
    assert not (only_folder(p) / "findings.json").exists()
    assert not list((tmp_path / "tmp").glob("kit-review-*"))
    assert git(p, "for-each-ref", REF_NS) == ""


def test_a_header_without_the_sandbox_line_stops_codex_at_once(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "noline")
    monkeypatch.setenv("FAKE_CODEX_DELAY", "30")
    p = code_project(tmp_path)
    t0 = time.monotonic()
    assert run(p) == 5
    assert time.monotonic() - t0 < 5 and "no sandbox line" in capsys.readouterr().err


def test_a_codex_that_exits_without_a_header_is_exit_5(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "noheader")
    p = code_project(tmp_path)
    assert run(p) == 5
    assert "no sandbox line" in capsys.readouterr().err


def test_a_large_brief_reaches_a_codex_that_reads_it_late(tmp_path, monkeypatch):
    record = install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_STDIN_DELAY", "0.6")
    p = code_project(tmp_path)
    claims = "".join(f"Claim {k}: x is {k}.\n" for k in range(10000))     # about 200 KB
    brief = write(tmp_path / "author.md", claims)
    assert run(p, "--brief", str(brief)) == 0
    assert claims in json.loads(record.read_text())["brief"]


def test_codex_failing_before_its_header_keeps_its_own_error(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch, mode="fail")
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "noheader")
    p = code_project(tmp_path)
    assert run(p) == 5
    assert json.loads((only_folder(p) / "meta.json").read_text())["notes"][0].startswith("codex exited 1")


def test_a_header_that_never_completes_stops_codex(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.setattr(codex_review, "HEADER_WAIT_S", 1.0)
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "noheader")
    monkeypatch.setenv("FAKE_CODEX_DELAY", "30")
    p = code_project(tmp_path)
    t0 = time.monotonic()
    assert run(p) == 5
    assert time.monotonic() - t0 < 15 and "no sandbox line" in capsys.readouterr().err


def test_a_failed_codex_with_a_wider_sandbox_reports_the_sandbox(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch, mode="fail")
    monkeypatch.setenv("FAKE_CODEX_SANDBOX", "danger-full-access")
    p = code_project(tmp_path)
    assert run(p) == 5
    assert "(sandbox: danger-full-access)" in capsys.readouterr().err


def test_a_project_error_during_the_run_is_recorded(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)

    def broken_copy(project, reviewed):
        raise KitError("git worktree add failed: disk full")
    monkeypatch.setattr(codex_review, "make_copy", broken_copy)
    assert run(p) == 2
    meta = json.loads((only_folder(p) / "meta.json").read_text())
    assert meta["status"] == "error" and meta["notes"] == ["git worktree add failed: disk full"]


def test_relative_brief_and_plan_are_named_by_absolute_paths(tmp_path, monkeypatch):
    """Codex runs in the copy, so a path relative to the caller's folder would name nothing there."""
    record = install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    caller = tmp_path / "caller"
    write(caller / "plans" / "task.md", "Task 3.\n")
    write(caller / "author.md", "Claims: none.\n")
    monkeypatch.chdir(caller)
    assert run(p, "--plan", "plans/task.md", "--brief", "author.md") == 0
    brief = json.loads(record.read_text())["brief"]
    assert f"Plan task: `{(caller / 'plans' / 'task.md').resolve()}`" in brief
    assert "Claims: none." in brief


def test_not_a_repository_is_exit_2(tmp_path, monkeypatch):
    install_fake_codex(tmp_path, monkeypatch)
    d = tmp_path / "plain"
    d.mkdir()
    assert run(d) == 2


def test_an_empty_project_means_the_cwd_which_must_be_the_project_root(tmp_path, monkeypatch, capsys):
    """The skill passes --project "${CLAUDE_PROJECT_DIR}", which is empty in Claude's Bash tool."""
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    write(p / "analysis" / "c.py", "w = 2\n")                      # a change to review
    paper = p / "paper"
    write(paper / "main.tex", "hello\n")
    init_repo(paper)                                                # the paper clone: a repo, not a kit project
    monkeypatch.chdir(paper)
    assert main(["--project", ""]) == 2
    assert main(["--project", "", "--status"]) == 2
    err = capsys.readouterr().err
    assert f"{paper} is not a research-kit project (no .claude/research.yml)" in err
    assert not (p / "notes" / "reviews").exists()
    assert main(["--project", "", "--status", "--out", "reviews"]) == 0     # --out: any repo, as the kit's own
    monkeypatch.chdir(p / "analysis")
    assert main(["--project", "", "--status"]) == 2
    assert "is not the top of a git work tree" in capsys.readouterr().err
    plain = tmp_path / "plain"
    plain.mkdir()
    assert main(["--project", str(plain), "--status"]) == 2
    assert main(["--project", str(tmp_path / "missing"), "--status"]) == 2
    monkeypatch.chdir(p)
    assert main(["--project", "", "--status"]) == 0
    assert capsys.readouterr().out.strip() == "review: none yet (3 code files changed in the last 20 commits)"
    assert main(["--project", ""]) == 0
    assert len(list((p / "notes" / "reviews").glob("*/meta.json"))) == 1


def test_the_review_folder_is_printed_even_when_codex_is_unavailable(tmp_path, monkeypatch, capsys):
    """The Claude-only fallback needs the folder that holds brief.md."""
    install_fake_codex(tmp_path, monkeypatch, mode="nologin")
    p = code_project(tmp_path)
    assert run(p) == 3
    assert f"codex_review: review folder {only_folder(p).resolve()}\n" in capsys.readouterr().out


def test_an_unexpected_error_is_exit_2_with_the_record_written(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)

    def broken_run(*args):
        raise ValueError("boom")
    monkeypatch.setattr(codex_review, "run_codex", broken_run)
    assert run(p) == 2
    assert "codex_review: ERROR: ValueError: boom" in capsys.readouterr().err
    meta = json.loads((only_folder(p) / "meta.json").read_text())
    assert meta["status"] == "error" and meta["finished"]
    assert not list((tmp_path / "tmp").glob("kit-review-*"))          # the copy was removed


def test_out_and_status_cli(tmp_path, monkeypatch, capsys):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    assert run(p, "--out", "docs/reviews") == 0
    assert len(list((p / "docs" / "reviews").glob("*-codex-*"))) == 1
    assert run(p, "--out", "docs/reviews", "--status") == 0
    assert capsys.readouterr().out.strip().endswith("review: up to date")


def test_validate():
    good = {"summary_markdown": "s", "findings": [], "verified": [], "not_checked": []}
    assert validate(good) == []
    assert validate({"findings": []})
    bad = {**good, "findings": [{"id": "F1", "severity": "huge", "category": "code bug", "file": "a",
                                 "line": "3", "claim": "c", "evidence": "e", "suggested_fix": "f"}]}
    problems = validate(bad)
    assert any("severity" in x for x in problems) and any("line" in x for x in problems)
