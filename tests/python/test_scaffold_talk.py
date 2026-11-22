import shutil
import struct
import subprocess
import zlib

import pytest

from build_fixture import bare_overleaf, set_config
from kitlib import KitError
from lint_numbers import lint_text
from scaffold import cmd_attach, cmd_new, cmd_new_talk, main

MAIN = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


def project(tmp_path, sub=None):
    """An attached project; with sub, the manuscript and its generated/ live in paper/<sub>/."""
    bare = bare_overleaf(tmp_path, {f"{sub}/main.tex" if sub else "main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    if sub:
        for key in ("numbers_tex", "notation_tex"):
            set_config(p, f"{key}: paper/generated/", f"{key}: paper/{sub}/generated/")
        set_config(p, '["*.tex", "sections/**/*.tex"]', f'["{sub}/main.tex"]')
    cmd_attach(str(bare), p)
    return p


def png(path):
    """A 1x1 white PNG."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b""))


def test_default_paths(tmp_path):
    p = project(tmp_path)
    tex = cmd_new_talk("jsm", p).read_text()
    assert lint_text(tex, "talk.tex") == []
    assert "\\graphicspath{{../../paper/figures/}}" in tex
    assert "\\input{../../paper/generated/numbers.tex}" in tex
    assert "\\input{../../paper/generated/notation.tex}" in tex
    assert "\\newcommand{\\papertables}{../../paper/tables}" in tex
    assert "{{" not in tex.replace("\\graphicspath{{", "")


@pytest.mark.parametrize("sub", ["draft", "current_version"])
def test_subfolder_manuscript_paths(tmp_path, sub):
    p = project(tmp_path, sub)
    tex = cmd_new_talk("jsm", p).read_text()
    assert lint_text(tex, "talk.tex") == []
    assert f"\\graphicspath{{{{../../paper/{sub}/figures/}}}}" in tex
    assert f"\\input{{../../paper/{sub}/generated/numbers.tex}}" in tex
    assert f"\\input{{../../paper/{sub}/generated/notation.tex}}" in tex
    assert f"\\newcommand{{\\papertables}}{{../../paper/{sub}/tables}}" in tex


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk not installed")
@pytest.mark.parametrize("sub", ["draft", "current_version"])
def test_subfolder_talk_compiles_with_numbers_tables_and_figures(tmp_path, sub):
    p = project(tmp_path, sub)
    base = p / "paper" / sub
    (base / "generated" / "numbers.tex").write_text("\\newcommand{\\nObs}{42}\n")
    (base / "generated" / "notation.tex").write_text("% generated\n")
    (base / "tables" / "t.tex").write_text("\\begin{tabular}{l}\\nObs\\end{tabular}\n")
    png(base / "figures" / "dot.png")
    out = cmd_new_talk("jsm", p)
    old = "\\item Every number is a macro from the paper's generated files."
    text = out.read_text()
    assert old in text
    out.write_text(text.replace(old, "\\item \\nObs{} \\input{\\papertables/t.tex} \\includegraphics{dot.png}"))
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "talk.tex"],
                       cwd=out.parent, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]


def test_manuscript_at_the_paper_root_without_generated_folder(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    set_config(p, "numbers_tex: paper/generated/numbers.tex", "numbers_tex: paper/numbers.tex")
    set_config(p, "notation_tex: paper/generated/notation.tex", "notation_tex: paper/notation.tex")
    cmd_attach(str(bare), p)
    tex = cmd_new_talk("jsm", p).read_text()
    assert "\\input{../../paper/numbers.tex}" in tex and "\\graphicspath{{../../paper/figures/}}" in tex


def test_symlinked_project_gives_the_same_relative_paths(tmp_path):
    p = project(tmp_path, "draft")
    link = tmp_path / "link"
    link.symlink_to(p)
    tex = cmd_new_talk("jsm", link).read_text()
    assert "\\input{../../paper/draft/generated/numbers.tex}" in tex
    assert (p / "slides" / "jsm" / "talk.tex").is_file()


def test_latex_special_character_in_a_paper_path_is_refused(tmp_path):
    p = project(tmp_path, "draft")
    for key in ("numbers_tex", "notation_tex"):
        set_config(p, f"{key}: paper/draft/", f"{key}: paper/draft%1/")
    (p / "paper" / "draft%1" / "generated").mkdir(parents=True)
    with pytest.raises(KitError, match="LaTeX special character"):
        cmd_new_talk("jsm", p)
    assert not (p / "slides" / "jsm").exists()


@pytest.mark.parametrize("blocker", ["slides", "slides/jsm"])
def test_a_file_in_the_way_is_an_error_not_a_traceback(tmp_path, blocker):
    p = project(tmp_path)
    if (p / "slides").is_dir():
        shutil.rmtree(p / "slides")
    (p / "slides").parent.mkdir(exist_ok=True)
    if blocker == "slides/jsm":
        (p / "slides").mkdir()
    (p / blocker).write_text("not a folder\n")
    with pytest.raises(KitError, match="cannot create"):
        cmd_new_talk("jsm", p)
    assert (p / blocker).read_text() == "not a folder\n"


def test_existing_outline_folder_is_fine_but_an_existing_talk_is_refused(tmp_path):
    p = project(tmp_path)
    (p / "slides" / "jsm").mkdir(parents=True)
    (p / "slides" / "jsm" / "outline.md").write_text("Locked\n")
    out = cmd_new_talk("jsm", p)
    out.write_text("mine\n")
    with pytest.raises(KitError, match="already exists"):
        cmd_new_talk("jsm", p)
    assert out.read_text() == "mine\n"


def test_paper_not_attached(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    with pytest.raises(KitError, match="isn't attached"):
        cmd_new_talk("jsm", p)
    assert not (p / "slides" / "jsm").exists()


@pytest.mark.parametrize("name", ["", "../jsm", "a/b", ".hidden", "-x", "two words"])
def test_bad_talk_names(tmp_path, name):
    p = project(tmp_path)
    with pytest.raises(KitError, match="talk name"):
        cmd_new_talk(name, p)
    assert not list(p.glob("**/talk.tex"))


def test_cli(tmp_path, capsys):
    p = project(tmp_path)
    assert main(["new-talk", "jsm", "--project", str(p)]) == 0
    assert "slides/jsm/talk.tex" in capsys.readouterr().out
    assert main(["new-talk", "jsm", "--project", str(p)]) == 2
    assert "already exists" in capsys.readouterr().err
