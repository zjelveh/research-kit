from build_fixture import minimal_project, write
from check_pointers import main


def test_existing_and_missing_paths(tmp_path, capsys):
    p = minimal_project(tmp_path)
    write(p / "notes" / "x.md", "x")
    write(p / "state" / "CURRENT_STATE.md",
          "See `notes/x.md:12` and `notes/gone.md` but not `v1.2` or `D-001` or `/kit:checkpoint`.\n")
    assert main(["--project", str(p)]) == 1
    out = capsys.readouterr().out
    assert "missing: notes/gone.md (state/CURRENT_STATE.md:1)" in out
    assert "notes/x.md" not in out


def test_all_present(tmp_path):
    p = minimal_project(tmp_path)
    write(p / "state" / "CURRENT_STATE.md", "Config in `.claude/research.yml`.\n")
    assert main(["--project", str(p)]) == 0


def test_missing_current_state_is_error(tmp_path):
    p = minimal_project(tmp_path)
    (p / "state" / "CURRENT_STATE.md").unlink()
    assert main(["--project", str(p)]) == 2


def test_non_path_tokens_ignored(tmp_path):
    p = minimal_project(tmp_path)
    (p / "notes" / "memos").mkdir(parents=True)
    write(p / "state" / "CURRENT_STATE.md",
          "Keys `lint.paper.globs`, `os.path`, `read/write`, `i.e`; dir `notes/memos/`.\n")
    assert main(["--project", str(p)]) == 0


def test_missing_directory_pointer_reported(tmp_path, capsys):
    p = minimal_project(tmp_path)
    write(p / "state" / "CURRENT_STATE.md", "See `notes/nothere/`.\n")
    assert main(["--project", str(p)]) == 1
    assert "missing: notes/nothere/" in capsys.readouterr().out
