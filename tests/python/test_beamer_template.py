import shutil
import subprocess
from pathlib import Path

import pytest

from lint_numbers import lint_text
from scaffold import render

KIT = Path(__file__).resolve().parents[2]
TEMPLATE = KIT / "plugins" / "kit" / "templates" / "beamer" / "talk.tex"


def test_template_lints_clean():
    assert lint_text(TEMPLATE.read_text(encoding="utf-8"), "talk.tex") == []


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk not installed")
def test_template_compiles_with_generated_inputs(tmp_path):
    proj = tmp_path / "proj"
    (proj / "paper" / "generated").mkdir(parents=True)
    (proj / "paper" / "figures").mkdir()
    (proj / "paper" / "generated" / "numbers.tex").write_text("% generated\n")
    (proj / "paper" / "generated" / "notation.tex").write_text("% generated\n")
    talk = proj / "slides" / "demo"
    talk.mkdir(parents=True)
    (talk / "talk.tex").write_text(render(TEMPLATE.read_text(encoding="utf-8"), {
        "FIGURES": "../../paper/figures", "TABLES": "../../paper/tables",
        "NUMBERS_TEX": "../../paper/generated/numbers.tex", "NOTATION_TEX": "../../paper/generated/notation.tex"}))
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "talk.tex"],
                       cwd=talk, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:]
    assert (talk / "talk.pdf").is_file()
