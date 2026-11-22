from build_fixture import minimal_project, write
from check_bib import main

BIB = """@article{smith2020,
  title = {A},
  doi = {10.1/x},
}
@book{jones2019,
  title = {B},
}
"""


def proj(tmp_path, tex):
    p = minimal_project(tmp_path)
    write(p / "paper" / "refs.bib", BIB)
    write(p / "paper" / "main.tex", tex)
    return p


def test_all_keys_present(tmp_path, capsys):
    p = proj(tmp_path, "\\citep[p.~2]{smith2020} and \\citet{jones2019}")
    assert main(["--project", str(p)]) == 0
    assert "no DOI or URL: jones2019" in capsys.readouterr().out


def test_missing_key_fails(tmp_path, capsys):
    p = proj(tmp_path, "\\cite{smith2020, ghost2021}")
    assert main(["--project", str(p)]) == 1
    assert "missing from .bib: ghost2021" in capsys.readouterr().out


def test_slides_citations_checked(tmp_path):
    p = proj(tmp_path, "none")
    write(p / "slides" / "t" / "talk.tex", "\\textcite{ghost2021}")
    assert main(["--project", str(p)]) == 1


def test_no_bib_with_citations_is_error(tmp_path):
    p = proj(tmp_path, "\\cite{smith2020}")
    (p / "paper" / "refs.bib").unlink()
    assert main(["--project", str(p)]) == 2


def test_commented_out_citation_ignored(tmp_path):
    p = proj(tmp_path, "% \\cite{old}\nText 50\\% \\cite{smith2020} % \\cite{ghost}")
    assert main(["--project", str(p)]) == 0


def test_nocite_star_ignored(tmp_path):
    p = proj(tmp_path, "\\nocite{*} \\cite{smith2020}")
    assert main(["--project", str(p)]) == 0


def test_one_line_entry_doi_detected(tmp_path, capsys):
    p = proj(tmp_path, "\\cite{oneline}")
    (p / "paper" / "refs.bib").write_text(BIB + "@article{oneline, title={x}, doi={10.1/y}}\n")
    assert main(["--project", str(p)]) == 0
    assert "oneline" not in capsys.readouterr().out


from build_fixture import CONFIG


def sub_proj(tmp_path, files, globs='["current_version/rp.tex"]'):
    p = minimal_project(tmp_path, CONFIG.replace('["main.tex", "sections/*.tex"]', globs))
    for name, text in files.items():
        write(p / "paper" / name, text)
    return p


def test_subfolder_manuscript_uses_its_named_bib(tmp_path):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{citations.bib}\n\\cite{smith2020}",
                            "current_version/citations.bib": BIB})
    assert main(["--project", str(p)]) == 0


def test_old_drafts_outside_the_globs_are_not_counted(tmp_path):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{citations.bib}\n\\cite{smith2020}",
                            "current_version/citations.bib": BIB,
                            "older_versions/v1.tex": "\\cite{ghost2021}",
                            "rp_submission/rp.tex": "\\cite{ghost2021}"})
    assert main(["--project", str(p)]) == 0


def test_inputs_are_followed_from_the_main_files_folder(tmp_path, capsys):
    p = sub_proj(tmp_path, {"draft/main.tex": "\\bibliography{dv}\n\\input{../Tables/t1}\n\\include{parts/intro}",
                            "draft/dv.bib": BIB,
                            "Tables/t1.tex": "\\cite{ghost2021}",
                            "draft/parts/intro.tex": "\\input{parts/deeper}",
                            "draft/parts/deeper.tex": "\\cite{ghost2022}"},
                 globs='["draft/main.tex"]')
    assert main(["--project", str(p)]) == 1
    out = capsys.readouterr().out
    assert "missing from .bib: ghost2021" in out and "missing from .bib: ghost2022" in out


def test_commented_input_is_not_followed(tmp_path):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{citations.bib}\n% \\input{old}\n\\cite{smith2020}",
                            "current_version/citations.bib": BIB,
                            "current_version/old.tex": "\\cite{ghost2021}"})
    assert main(["--project", str(p)]) == 0


def test_bibliography_list_reads_every_named_file(tmp_path):
    extra = "@misc{extra2022, title = {E}, url = {https://x}}\n"
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\bibliography{refs,extra}\n\\cite{smith2020,extra2022}",
                            "current_version/refs.bib": BIB, "current_version/extra.bib": extra})
    assert main(["--project", str(p)]) == 0


def test_named_bib_that_does_not_exist_is_an_error(tmp_path, capsys):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{nope.bib}\n\\cite{smith2020}",
                            "current_version/citations.bib": BIB})
    assert main(["--project", str(p)]) == 2
    assert "nope.bib" in capsys.readouterr().err


def test_unnamed_bib_beside_the_manuscript_is_used(tmp_path):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\cite{smith2020}",
                            "current_version/citations.bib": BIB})
    assert main(["--project", str(p)]) == 0


def test_bib_named_by_slides_counts(tmp_path):
    p = proj(tmp_path, "\\cite{smith2020}")
    write(p / "slides" / "t" / "talk.tex", "\\addbibresource{talk.bib}\n\\textcite{talkonly2023}")
    write(p / "slides" / "t" / "talk.bib", "@misc{talkonly2023, title = {T}, url = {https://y}}\n")
    assert main(["--project", str(p)]) == 0


def test_paper_globs_matching_nothing_is_an_error(tmp_path, capsys):
    p = sub_proj(tmp_path, {"draft/paper.tex": "\\cite{smith2020}", "draft/refs.bib": BIB},
                 globs='["draft/main.tex"]')
    assert main(["--project", str(p)]) == 2
    assert "lint.paper.globs" in capsys.readouterr().err


def test_paper_keys_need_the_papers_bib_not_the_slides(tmp_path, capsys):
    p = proj(tmp_path, "\\cite{talkonly2023}")
    write(p / "slides" / "t" / "talk.tex", "\\addbibresource{talk.bib}\n\\textcite{talkonly2023}")
    write(p / "slides" / "t" / "talk.bib", "@misc{talkonly2023, title = {T}, url = {https://y}}\n")
    assert main(["--project", str(p)]) == 1
    assert "missing from .bib: talkonly2023" in capsys.readouterr().out


def test_a_shared_file_is_resolved_from_every_root(tmp_path, capsys):
    p = sub_proj(tmp_path, {"main/paper.tex": "\\bibliography{refs}\n\\input{../appendix/app}",
                            "main/refs.bib": BIB,
                            "appendix/app.tex": "\\input{tables/t2}",
                            "main/tables/t2.tex": "\\cite{ghost2021}"},
                 globs='["main/paper.tex", "appendix/app.tex"]')
    assert main(["--project", str(p)]) == 1
    assert "missing from .bib: ghost2021" in capsys.readouterr().out


def test_braceless_input_is_followed(tmp_path):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{citations.bib}\n\\input sections/intro\n",
                            "current_version/citations.bib": BIB,
                            "current_version/sections/intro.tex": "\\cite{ghost2021}"})
    assert main(["--project", str(p)]) == 1


def test_unresolved_input_is_warned_about(tmp_path, capsys):
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\addbibresource{citations.bib}\n\\input{\\secdir/intro}\n\\cite{smith2020}",
                            "current_version/citations.bib": BIB})
    assert main(["--project", str(p)]) == 0
    assert "\\secdir/intro" in capsys.readouterr().err


def test_bib_from_the_tex_distribution_and_remote_resources_are_not_errors(tmp_path, monkeypatch):
    import check_bib
    system_bib = write(tmp_path / "texmf" / "IEEEabrv.bib", "@string{IEEE = {IEEE}}\n")
    monkeypatch.setattr(check_bib, "kpsewhich", lambda name: str(system_bib) if name == "IEEEabrv.bib" else None)
    p = sub_proj(tmp_path, {"current_version/rp.tex": "\\bibliography{IEEEabrv,refs}\n"
                            "\\addbibresource[location=remote]{https://example.org/x.bib}\n\\cite{smith2020}",
                            "current_version/refs.bib": BIB})
    assert main(["--project", str(p)]) == 0


def test_input_through_a_path_macro_is_followed(tmp_path, capsys):
    """A talk inputs tables as \\input{\\papertables/<file>}; scaffold.py new-talk defines the macro."""
    p = proj(tmp_path, "\\cite{smith2020}")
    write(p / "paper" / "tables" / "t.tex", "\\cite{ghost2021}")
    write(p / "slides" / "t" / "talk.tex",
          "\\newcommand{\\papertables}{../../paper/tables}\n\\input{\\papertables/t.tex}\n")
    assert main(["--project", str(p)]) == 1
    captured = capsys.readouterr()
    assert "ghost2021" in captured.out and "not found" not in captured.err


def test_path_macro_defined_in_an_input_file_is_used(tmp_path, capsys):
    p = proj(tmp_path, "\\cite{smith2020}")
    write(p / "paper" / "tables" / "t.tex", "\\cite{ghost2021}")
    write(p / "slides" / "t" / "pre.tex", "\\newcommand*{\\papertables}{../../paper/tables}\n")
    write(p / "slides" / "t" / "talk.tex", "\\input{pre}\n\\input{\\papertables/t.tex}\n")
    assert main(["--project", str(p)]) == 1
    captured = capsys.readouterr()
    assert "ghost2021" in captured.out and "not found" not in captured.err


def test_path_macro_from_the_talk_reaches_a_sibling_root(tmp_path, capsys):
    """slides/*/*.tex makes backup.tex a root of its own, sorted before talk.tex, which defines the macro."""
    p = proj(tmp_path, "\\cite{smith2020}")
    write(p / "paper" / "tables" / "t.tex", "\\cite{ghost2021}")
    write(p / "slides" / "t" / "backup.tex", "\\input{\\papertables/t.tex}\n")
    write(p / "slides" / "t" / "talk.tex", "\\newcommand{\\papertables}{../../paper/tables}\n\\input{backup}\n")
    assert main(["--project", str(p)]) == 1
    captured = capsys.readouterr()
    assert "ghost2021" in captured.out and "not found" not in captured.err
