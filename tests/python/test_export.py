"""Export of a public release (shareable-kit spec §4). Made-up names only: this file is exported too."""
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[2] / "bin"
sys.path.insert(0, str(BIN))
spec = importlib.util.spec_from_file_location("export_public", BIN / "export_public.py")
export_public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_public)

PLUGIN_JSON = "plugins/kit/.claude-plugin/plugin.json"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def write(root: Path, rel: str, text: str, mode: int | None = None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if mode is not None:
        p.chmod(mode)


def commit_all(repo: Path, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def repos(tmp_path):
    src, pub = tmp_path / "src", tmp_path / "pub"
    for r in (src, pub):
        r.mkdir()
        git(r, "init", "-q", "-b", "main")
    write(src, ".claude-plugin/marketplace.json", json.dumps({"name": "research-kit", "owner": {"name": "acme-owner"}}))
    write(src, PLUGIN_JSON, json.dumps({"name": "kit", "version": "1.0.0"}))
    write(src, "plugins/kit/bin/kit", "#!/bin/sh\necho kit\n", 0o755)
    write(src, ".gitignore", ".venv\n")
    write(src, "README.md", "install acme-owner/research-kit\n")
    for rel in ("docs/specs/s.md", "docs/plans/p.md", "docs/measurements/m.md", "docs/reviews/r.md",
                "bin/measure_hook_limit.py"):
        write(src, rel, "private\n")
    write(src, "private/leak_terms.txt", "# names\nsecretproj\n")
    commit_all(src)
    return src, pub


def files_of(repo: Path) -> set[str]:
    return set(git(repo, "ls-files").split())


def blob(repo: Path, rev: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "blob", rev], capture_output=True, check=True).stdout


def test_first_export(repos, capsys, monkeypatch):
    src, pub = repos
    monkeypatch.setenv("GIT_COMMITTER_NAME", "kit-committer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "kit-committer@example.invalid")
    assert export_public.export(pub, "release 1", src=src) == 0
    out = capsys.readouterr()
    assert "1 private terms from private/leak_terms.txt" in out.err
    assert ("as author kit-test <kit-test@example.invalid>, committer kit-committer <kit-committer@example.invalid>. "
            "Not pushed.") in out.out
    assert files_of(pub) == {".claude-plugin/marketplace.json", PLUGIN_JSON, "plugins/kit/bin/kit",
                             ".gitignore", "README.md"}
    assert not (pub / "docs").exists() and not (pub / "private").exists()
    assert os.stat(pub / "plugins/kit/bin/kit").st_mode & stat.S_IXUSR
    assert git(pub, "ls-files", "-s", "plugins/kit/bin/kit").startswith("100755")
    assert git(pub, "log", "--format=%s") == "release 1\n"
    assert git(pub, "status", "--porcelain") == ""


def test_uncommitted_changes_in_src_are_refused(repos, capsys):
    src, pub = repos
    write(src, "README.md", "changed\n")
    assert export_public.main([str(pub), "-m", "x"], src=src) == 2
    assert "commit first" in capsys.readouterr().err
    assert files_of(pub) == set()


def test_leak_refuses_and_writes_nothing(repos, capsys):
    src, pub = repos
    write(src, "README.md", "about SecretProj\n")
    commit_all(src)
    assert export_public.export(pub, "x", src=src) == 1
    out = capsys.readouterr()
    assert "README.md:1: 'secretproj'" in out.out and "nothing was written" in out.err
    assert list(pub.iterdir()) == [pub / ".git"]


def test_no_terms_file_still_checks_fixed_patterns(repos, capsys):
    src, pub = repos
    git(src, "rm", "-q", "-r", "private")
    write(src, "notes.md", "see /" + "home/me\n")
    commit_all(src)
    assert export_public.export(pub, "x", src=src) == 1
    assert "no private/leak_terms.txt; checking fixed patterns and the account name only" in capsys.readouterr().err


def test_nothing_to_release(repos, capsys):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert "nothing to release" in capsys.readouterr().out
    assert git(pub, "rev-list", "--count", "HEAD") == "1\n"


def test_plugin_change_needs_a_new_version(repos, capsys):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    write(src, "plugins/kit/bin/kit", "#!/bin/sh\necho kit 2\n", 0o755)
    commit_all(src)
    head = git(pub, "rev-parse", "HEAD")
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2  # export() raises Refused; main() maps it to 2
    assert "bump" in capsys.readouterr().err
    assert git(pub, "rev-parse", "HEAD") == head and git(pub, "status", "--porcelain") == ""
    assert (pub / "plugins/kit/bin/kit").read_text() == "#!/bin/sh\necho kit\n"
    write(src, PLUGIN_JSON, json.dumps({"name": "kit", "version": "1.0.1"}))
    commit_all(src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert (pub / "plugins/kit/bin/kit").read_text() == "#!/bin/sh\necho kit 2\n"


def test_change_outside_the_plugin_needs_no_new_version(repos):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    write(src, "README.md", "install acme-owner/research-kit, then run setup\n")
    commit_all(src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert git(pub, "rev-list", "--count", "HEAD") == "2\n"


def test_deleted_files_leave_and_ignored_files_stay(repos):
    src, pub = repos
    write(src, "old.md", "old\n")
    commit_all(src)
    export_public.export(pub, "release 1", src=src)
    (pub / ".venv").mkdir()
    (pub / ".venv" / "keep").write_text("x")
    git(src, "rm", "-q", "old.md")
    commit_all(src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert not (pub / "old.md").exists() and (pub / ".venv" / "keep").exists()


def test_public_repo_must_be_a_separate_clean_repo(repos, tmp_path, capsys):
    src, pub = repos
    plain = tmp_path / "plain"
    plain.mkdir()
    assert export_public.main([str(plain), "-m", "x"], src=src) == 2
    assert "is not the top folder of a git repo" in capsys.readouterr().err
    assert export_public.main([str(src / "plugins"), "-m", "x"], src=src) == 2
    assert "is not the top folder of a git repo" in capsys.readouterr().err
    assert export_public.main([str(src), "-m", "x"], src=src) == 2
    assert "must be outside" in capsys.readouterr().err
    write(pub, "stray.md", "x\n")
    assert export_public.main([str(pub), "-m", "x"], src=src) == 2
    assert "has uncommitted changes" in capsys.readouterr().err


def has_commit(repo: Path) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "HEAD"],
                          capture_output=True).returncode == 0


def test_ignored_files_never_enter_a_release(repos):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    write(pub, ".venv/notes", "/" + "home/x\n")  # ignored in pub, so never checked
    write(src, ".gitignore", "")
    commit_all(src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert ".venv/notes" not in files_of(pub)
    assert (pub / ".venv/notes").exists()


def test_untracked_files_hidden_by_config_are_refused(repos, capsys):
    src, pub = repos
    git(pub, "config", "status.showUntrackedFiles", "no")
    write(pub, "scratch.txt", "x\n")
    assert export_public.main([str(pub), "-m", "x"], src=src) == 2
    assert "uncommitted" in capsys.readouterr().err
    assert not has_commit(pub)


def test_public_repo_may_not_share_the_private_history(repos, tmp_path, capsys):
    src, _ = repos
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(src), str(clone))
    head = git(clone, "rev-parse", "HEAD")
    assert export_public.main([str(clone), "-m", "x"], src=src) == 2
    assert "shares history" in capsys.readouterr().err
    assert git(clone, "rev-parse", "HEAD") == head
    git(src, "worktree", "add", "-q", str(tmp_path / "wt"))
    assert export_public.main([str(tmp_path / "wt"), "-m", "x"], src=src) == 2
    assert "shares history" in capsys.readouterr().err


def test_history_shared_through_another_branch_is_refused(repos, tmp_path, capsys):
    """Every root commit of src counts, not only HEAD's: a clone of an orphan branch holds private history too."""
    src, _ = repos
    git(src, "checkout", "-q", "--orphan", "side")
    commit_all(src, "side root")
    git(src, "checkout", "-q", "main")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "--single-branch", "-b", "side", f"file://{src}", str(clone))  # side's objects only
    assert export_public.main([str(clone), "-m", "x"], src=src) == 2
    assert "shares history" in capsys.readouterr().err
    assert git(clone, "log", "--format=%s") == "side root\n"


def test_shallow_clone_is_refused(repos, tmp_path, capsys):
    """A shallow clone of src lacks src's root commit, but its HEAD is src's commit with the private files."""
    src, _ = repos
    write(src, "README.md", "install acme-owner/research-kit, then run setup\n")
    commit_all(src)
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{src}", str(shallow))
    assert export_public.main([str(shallow), "-m", "x"], src=src) == 2
    assert "shallow" in capsys.readouterr().err
    assert git(shallow, "rev-list", "--count", "HEAD") == "1\n"


def test_a_tracked_symlink_stays_a_symlink(repos):
    src, pub = repos
    (src / "plugins/kit/link").symlink_to("bin/kit")
    commit_all(src)
    assert export_public.export(pub, "release 1", src=src) == 0
    write(src, "README.md", "install acme-owner/research-kit, then run setup\n")
    commit_all(src)
    assert export_public.export(pub, "release 2", src=src) == 0
    assert git(pub, "ls-files", "-s", "plugins/kit/link").startswith("120000")
    assert os.readlink(pub / "plugins/kit/link") == "bin/kit"


def test_terms_file_without_terms_is_refused(repos, capsys):
    src, pub = repos
    write(src, "private/leak_terms.txt", "# comment\n")
    commit_all(src)
    assert export_public.main([str(pub), "-m", "x"], src=src) == 2
    assert "has no terms" in capsys.readouterr().err
    assert not has_commit(pub)


def test_terms_file_with_a_byte_order_mark(repos):
    src, pub = repos
    (src / "private/leak_terms.txt").write_bytes(b"\xef\xbb\xbfsecretproj\n")
    write(src, "README.md", "about SecretProj\n")
    commit_all(src)
    assert export_public.export(pub, "x", src=src) == 1
    assert not has_commit(pub)


def test_commit_message_is_checked(repos, capsys):
    src, pub = repos
    assert export_public.export(pub, "release with secretproj", src=src) == 1
    assert "commit message: 'secretproj'" in capsys.readouterr().out
    assert not has_commit(pub) and list(pub.iterdir()) == [pub / ".git"]


def test_public_repo_created_with_a_readme(repos):
    src, pub = repos
    write(pub, "README.md", "# research-kit\n")
    commit_all(pub, "Initial commit")
    assert export_public.export(pub, "release 1", src=src) == 0
    assert files_of(pub) == {".claude-plugin/marketplace.json", PLUGIN_JSON, "plugins/kit/bin/kit",
                             ".gitignore", "README.md"}
    assert git(pub, "log", "--format=%s") == "release 1\nInitial commit\n"
    assert (pub / "README.md").read_text() == "install acme-owner/research-kit\n"
    assert git(pub, "status", "--porcelain", "--untracked-files=all") == ""


def test_plugin_json_without_a_version_is_refused(repos, capsys):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    write(src, PLUGIN_JSON, json.dumps({"name": "kit"}))
    commit_all(src)
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    assert "version" in capsys.readouterr().err
    assert git(pub, "rev-list", "--count", "HEAD") == "1\n"


def test_mode_change_in_the_plugin_needs_a_new_version(repos, capsys):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    (src / "plugins/kit/bin/kit").chmod(0o644)
    commit_all(src)
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    assert "bump" in capsys.readouterr().err


def test_removed_plugin_file_needs_a_new_version(repos, capsys):
    src, pub = repos
    write(src, "plugins/kit/extra.md", "extra\n")
    commit_all(src)
    export_public.export(pub, "release 1", src=src)
    git(src, "rm", "-q", "plugins/kit/extra.md")
    commit_all(src)
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    assert "bump" in capsys.readouterr().err


def test_a_clean_filter_in_the_public_repo_cannot_change_the_release(repos):
    """The filter comes from the public repo's own config and info/attributes; the checked bytes are committed."""
    src, pub = repos
    git(pub, "config", "filter.inject.clean", "sed s/install/injected/")
    (pub / ".git/info/attributes").write_text("README.md filter=inject\n")
    assert export_public.export(pub, "release 1", src=src) == 0
    assert blob(pub, "HEAD:README.md") == b"install acme-owner/research-kit\n"


def test_line_endings_are_committed_byte_for_byte(repos, tmp_path):
    """core.autocrlf and a text attribute (from an attributes file the public repo's config names) would turn
    CRLF into LF on git add."""
    src, pub = repos
    (src / "notes").mkdir()
    (src / "notes/win.txt").write_bytes(b"one\r\ntwo\r\n")
    (src / "notes/mixed.md").write_bytes(b"one\r\ntwo\n")
    commit_all(src)
    git(pub, "config", "core.autocrlf", "true")
    (tmp_path / "attributes").write_text("*.md text eol=lf\n")
    git(pub, "config", "core.attributesFile", str(tmp_path / "attributes"))
    assert export_public.export(pub, "release 1", src=src) == 0
    assert blob(pub, "HEAD:notes/win.txt") == b"one\r\ntwo\r\n"
    assert blob(pub, "HEAD:notes/mixed.md") == b"one\r\ntwo\n"


def test_ignored_files_where_the_release_puts_a_path_are_refused(repos, capsys):
    """reset --hard would overwrite or delete them: an ignored file at a release path, inside a path the release
    makes a file, or where the release needs a folder."""
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    (pub / ".git/info/exclude").write_text("NOTES.md\nscratch/\nbuild\n")
    write(pub, "NOTES.md", "local notes\n")
    write(pub, "scratch/keep.txt", "local\n")
    write(pub, "build", "local\n")
    write(src, "NOTES.md", "public notes\n")
    write(src, "scratch", "now a file\n")
    write(src, "build/out.md", "out\n")
    commit_all(src)
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    err = capsys.readouterr().err
    for p, r in (("NOTES.md", "NOTES.md"), ("scratch/keep.txt", "scratch"), ("build", "build/out.md")):
        assert f"{pub.resolve()}: ignored file {p} is where the release puts {r}; move it, then rerun" in err
    assert git(pub, "log", "--format=%s") == "release 1\n"
    assert (pub / "NOTES.md").read_text() == "local notes\n" and (pub / "scratch/keep.txt").read_text() == "local\n"
    assert (pub / "build").read_text() == "local\n"


@pytest.mark.parametrize("released", [False, True])
def test_a_head_moved_meanwhile_is_kept(repos, monkeypatch, capsys, released):
    """update-ref checks HEAD's old value, unborn included, so a commit made in the public repo during the export
    is not overwritten."""
    src, pub = repos
    if released:
        export_public.export(pub, "release 1", src=src)
        write(src, "README.md", "install acme-owner/research-kit, then run setup\n")
        commit_all(src)
    real_git = export_public.git

    def racing_git(repo, *args, **kw):
        if args[:1] == ("commit-tree",):
            write(pub, "other.md", "other\n")
            commit_all(pub, "made meanwhile")
        return real_git(repo, *args, **kw)
    monkeypatch.setattr(export_public, "git", racing_git)
    assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    assert "update-ref" in capsys.readouterr().err
    assert git(pub, "log", "-1", "--format=%s") == "made meanwhile\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into any folder")
def test_a_failure_after_head_moves_says_how_to_recover(repos, capsys):
    src, pub = repos
    export_public.export(pub, "release 1", src=src)
    write(src, "plugins/kit/bin/new", "x\n")
    write(src, PLUGIN_JSON, json.dumps({"name": "kit", "version": "1.0.1"}))
    commit_all(src)
    (pub / "plugins/kit/bin").chmod(0o555)
    try:
        assert export_public.main([str(pub), "-m", "release 2"], src=src) == 2
    finally:
        (pub / "plugins/kit/bin").chmod(0o755)
    head, p = git(pub, "rev-parse", "HEAD").strip(), pub.resolve()
    assert git(pub, "log", "-1", "--format=%s") == "release 2\n"
    assert (f"export_public: HEAD in {p} is now {head}, but its files are not updated: fix the cause, then run "
            f"git -C {p} reset --hard\n") in capsys.readouterr().err
    git(pub, "reset", "-q", "--hard")
    assert (pub / "plugins/kit/bin/new").read_text() == "x\n"
    assert export_public.export(pub, "release 2", src=src) == 0
    assert "nothing to release" in capsys.readouterr().out
