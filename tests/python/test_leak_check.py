"""Leak check for the public export (shareable-kit spec §1). Patterns are built from parts, because this file
is exported and scanned too."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[2] / "bin"
spec = importlib.util.spec_from_file_location("leak_check", BIN / "leak_check.py")
leak_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leak_check)

OWNER = "acme-owner"
PROJ = "/" + "projects/"
HOME = "/" + "home/"
TAG = "(user" + ", 2026-01-02)"


def make_tree(root: Path, files: dict[str, str]) -> Path:
    mp = root / ".claude-plugin" / "marketplace.json"
    mp.parent.mkdir(parents=True)
    mp.write_text(json.dumps({"name": "research-kit", "owner": {"name": OWNER}}))
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def test_clean_tree(tmp_path):
    t = make_tree(tmp_path, {"README.md": "install from acme-owner/research-kit\n", "a/b.md": "fine\n"})
    assert leak_check.scan(t) == []
    assert leak_check.main([str(t)]) == 0


@pytest.mark.parametrize("bad", [PROJ + "x", HOME + "me", TAG])
def test_fixed_patterns(tmp_path, bad):
    t = make_tree(tmp_path, {"plugins/kit/skills/x/SKILL.md": f"line one\nsee {bad}\n"})
    hits = leak_check.scan(t)
    assert len(hits) == 1 and hits[0].startswith("plugins/kit/skills/x/SKILL.md:2:")


def test_account_name_only_in_allowed_files(tmp_path):
    allowed = {rel: f"by {OWNER}\n" for rel in ("README.md", "LICENSE", "plugins/kit/.claude-plugin/plugin.json")}
    t = make_tree(tmp_path, {**allowed, "plugins/kit/scripts/x.py": f"# {OWNER.upper()}\n"})
    hits = leak_check.scan(t)
    assert hits == [f"plugins/kit/scripts/x.py:1: {OWNER!r}"]


def test_terms_match_contents_and_path_names_ignoring_case(tmp_path):
    t = make_tree(tmp_path / "tree", {"notes/SecretProj.md": "nothing\n", "b.md": "about SECRETPROJ here\n"})
    terms = tmp_path / "terms.txt"  # outside the scanned tree
    terms.write_text("# private names\n\nsecretproj\n")
    assert leak_check.read_terms(terms) == ["secretproj"]
    hits = leak_check.scan(t, leak_check.read_terms(terms))
    assert hits == ["b.md:1: 'secretproj'", "notes/SecretProj.md: path contains 'secretproj'"]
    assert leak_check.main([str(t), "--terms", str(terms)]) == 1


def test_git_folder_is_skipped(tmp_path):
    t = make_tree(tmp_path, {".git/config": f"url = {HOME}x\n"})
    assert leak_check.scan(t) == []


def test_symlinked_folder_is_listed_by_its_target(tmp_path):
    t = make_tree(tmp_path / "tree", {})
    (tmp_path / "secretproj-dir").mkdir()  # exists, so os.walk lists the link as a folder
    (t / "link").symlink_to("../secretproj-dir", target_is_directory=True)
    assert "link" in leak_check.tree_files(t)
    assert leak_check.scan(t, ["secretproj"]) == ["link:1: 'secretproj'"]


def test_files_argument_limits_the_scan(tmp_path):
    t = make_tree(tmp_path, {"a.md": PROJ + "\n", "b.md": "ok\n"})
    assert leak_check.scan(t, files=["b.md"]) == []


def test_missing_marketplace_is_a_usage_error(tmp_path, capsys):
    assert leak_check.main([str(tmp_path)]) == 2
    assert "marketplace.json" in capsys.readouterr().err


def test_missing_terms_file_is_a_usage_error(tmp_path):
    t = make_tree(tmp_path, {})
    assert leak_check.main([str(t), "--terms", str(tmp_path / "nope.txt")]) == 2


def test_terms_file_with_a_byte_order_mark(tmp_path):
    t = make_tree(tmp_path / "tree", {"b.md": "about SecretProj\n"})
    terms = tmp_path / "terms.txt"
    terms.write_bytes(b"\xef\xbb\xbfsecretproj\n")
    assert leak_check.read_terms(terms) == ["secretproj"]
    assert leak_check.scan(t, leak_check.read_terms(terms)) == ["b.md:1: 'secretproj'"]


def test_a_file_that_is_not_utf8_is_a_hit(tmp_path):
    t = make_tree(tmp_path, {})
    (t / "latin.txt").write_bytes(b"caf\xe9\n")
    (t / "secretproj.dat").write_bytes(b"\xff\n")  # its path name is still checked
    assert leak_check.scan(t, ["secretproj"]) == [
        "latin.txt: not UTF-8 text, so it can't be checked",
        "secretproj.dat: not UTF-8 text, so it can't be checked",
        "secretproj.dat: path contains 'secretproj'"]
    assert leak_check.main([str(t)]) == 1


def test_matching_folds_case_fully(tmp_path):
    t = make_tree(tmp_path, {"a.md": "STRASSE\n"})
    assert leak_check.scan(t, ["straße"]) == ["a.md:1: 'straße'"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_unreadable_folder_is_an_error(tmp_path):
    t = make_tree(tmp_path, {"locked/a.md": "x\n"})
    (t / "locked").chmod(0)
    try:
        with pytest.raises(PermissionError):
            leak_check.tree_files(t)
        assert leak_check.main([str(t)]) == 2
    finally:
        (t / "locked").chmod(0o755)


def test_exportable_tree_is_clean():
    """Every tracked file that a release would export, as it stands in the working tree."""
    root = BIN.parent
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True)
    if r.returncode:
        pytest.skip("not a git checkout")
    sys.path.insert(0, str(BIN))
    import export_public
    files = [f for f in r.stdout.split("\0") if f and not export_public.excluded(f) and os.path.lexists(root / f)]
    terms_file = root / "private" / "leak_terms.txt"
    terms = leak_check.read_terms(terms_file) if terms_file.is_file() else ()
    assert leak_check.scan(root, terms, files) == []
