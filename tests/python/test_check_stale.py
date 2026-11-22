from build_fixture import minimal_project, write
from check_stale import main


def proj(tmp_path):
    p = minimal_project(tmp_path)
    write(p / "paper" / "main.tex", "The estimand is\n  well defined here.\n")
    write(p / "notes" / "memos" / "2026-10-07-x.md", "The estimand is well defined here.\n")
    write(p / "notes" / "lit" / "searches" / "s.md", "The estimand is well defined here.\n")
    write(p / "slides" / "t" / "talk.tex", "nothing\n")
    return p


def test_wrapped_phrase_is_found(tmp_path, capsys):
    p = proj(tmp_path)
    assert main(["--project", str(p), "estimand is well defined"]) == 1
    out = capsys.readouterr().out
    assert "STILL PRESENT (1x) paper/main.tex" in out


def test_memos_and_searches_excluded(tmp_path, capsys):
    p = proj(tmp_path)
    (p / "paper" / "main.tex").write_text("other\n")
    assert main(["--project", str(p), "estimand is well defined"]) == 0
    assert "clean" in capsys.readouterr().out


def test_no_phrase_is_usage_error(tmp_path):
    assert main(["--project", str(proj(tmp_path))]) == 2


def sub_proj(tmp_path, files, globs):
    from build_fixture import CONFIG
    p = minimal_project(tmp_path, CONFIG.replace('["main.tex", "sections/*.tex"]', globs))
    for name, text in files.items():
        write(p / "paper" / name, text)
    return p


def test_only_the_manuscript_is_scanned_not_frozen_copies(tmp_path, capsys):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{refs.bib}\n\\input{sec}\n",
                            "current_version/sec.tex": "The old claim.\n",
                            "current_version/refs.bib": "@misc{a, note = {The old claim.}}\n",
                            "rp_submission/rp.tex": "The old claim.\n",
                            "older_versions/v1.tex": "The old claim.\n"},
                 '["current_version/rp.tex"]')
    assert main(["--project", str(p), "The old claim."]) == 1
    out = capsys.readouterr().out
    assert "paper/current_version/sec.tex" in out and "paper/current_version/refs.bib" in out
    assert "rp_submission" not in out and "older_versions" not in out


def test_inputs_outside_the_main_files_folder_are_scanned(tmp_path, capsys):
    p = sub_proj(tmp_path, {"draft/main.tex": "\\input{../Tables/t1}\n", "Tables/t1.tex": "The old claim.\n",
                            "draft/archive/old.tex": "The old claim.\n"},
                 '["draft/main.tex"]')
    assert main(["--project", str(p), "The old claim."]) == 1
    out = capsys.readouterr().out
    assert "paper/Tables/t1.tex" in out and "archive" not in out


def test_paper_globs_matching_nothing_is_an_error(tmp_path, capsys):
    p = sub_proj(tmp_path, {"other.tex": "x\n"}, '["draft/main.tex"]')
    assert main(["--project", str(p), "x"]) == 2
    assert "lint.paper.globs" in capsys.readouterr().err


def test_companion_files_beside_the_main_file_are_scanned_but_not_subfolders(tmp_path, capsys):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "x\n", "current_version/title_page.tex": "The old claim.\n",
                            "current_version/old/rp.tex": "The old claim.\n"},
                 '["current_version/rp.tex"]')
    assert main(["--project", str(p), "The old claim."]) == 1
    out = capsys.readouterr().out
    assert "paper/current_version/title_page.tex" in out and "current_version/old" not in out


def test_symlinked_paper_folder_is_still_scanned(tmp_path, capsys):
    p = sub_proj(tmp_path, {}, '["main.tex"]')
    real = tmp_path / "elsewhere" / "paper"
    write(real / "main.tex", "\\input{sec}\n")
    write(real / "sec.tex", "The old claim.\n")
    (p / "paper").symlink_to(real)
    assert main(["--project", str(p), "The old claim."]) == 1
    assert "STILL PRESENT (1x) paper/sec.tex" in capsys.readouterr().out


def test_unresolved_input_is_warned_about(tmp_path, capsys):
    p = sub_proj(tmp_path, {"main.tex": "\\input{\\secdir/intro}\n"}, '["main.tex"]')
    assert main(["--project", str(p), "The old claim."]) == 0
    assert "\\secdir/intro" in capsys.readouterr().err
