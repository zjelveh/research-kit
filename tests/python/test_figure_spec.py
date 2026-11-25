from pathlib import Path

import pytest

import figure_spec as fs
from build_fixture import minimal_project, write
from figures_fixture import spec, vocab
from kitlib import KitError


def test_spec_paths_include_panels_and_read_spec(tmp_path):
    p = minimal_project(tmp_path)
    write(p / "notes/figures/a.yml", "figure: a\n")
    write(p / "notes/figures/b/A.yml", "figure: b\npanel: A\n")
    write(p / "notes/figures/b/B.yml", "figure: b\npanel: B\n")
    paths = fs.spec_paths(p)
    assert [q.relative_to(p).as_posix() for q in paths] == ["notes/figures/a.yml", "notes/figures/b/A.yml",
                                                           "notes/figures/b/B.yml"]
    s = fs.read_spec(paths[1])
    assert fs.label(s) == "b/A" and fs.label(fs.read_spec(paths[0])) == "a"
    write(p / "notes/figures/bad.yml", "figure: [unclosed\n")
    with pytest.raises(KitError, match="bad.yml"):
        fs.read_spec(p / "notes/figures/bad.yml")


def test_shape_counts_keys_without_a_role():
    s = spec()
    assert fs.shape(s) == "1-key"
    s["what"]["keys"].append({"name": "panel", "type": "categorical", "role": "facet"})
    assert fs.shape(s) == "1-key"
    s["what"]["keys"].append({"name": "year", "type": "ordinal"})
    assert fs.shape(s) == "2-keys"
    s["what"]["keys"] += [{"name": "a", "type": "ordinal"}, {"name": "b", "type": "ordinal"}]
    assert fs.shape(s) is None
    s["what"]["spatial"] = "regions"
    assert fs.shape(s) == "geographic"


def test_substitutes_chain():
    v = vocab()
    assert fs.substitution_steps("ordinal", "quantitative", v) == 1
    assert fs.substitution_steps("categorical", "quantitative", v) == 2
    assert fs.substitution_steps("quantitative", "ordinal", v) is None
    assert fs.fits("categorical", "ordinal", v) and fs.fits("categorical", "quantitative", v)
    assert fs.fits("ordinal", "quantitative", v) and not fs.fits("quantitative", "categorical", v)
    assert not fs.fits("quantitative", "ordinal", v)


def test_focus_defaults_to_the_first_value_without_a_role():
    s = spec()
    s["what"]["values"].insert(0, {"name": "low", "type": "quantitative", "role": "interval"})
    assert fs.focus(s) == "estimate"
    s["why"]["focus"] = "group"
    assert fs.focus(s) == "group"
    s["why"]["focus"] = {"derived": "change from start to end"}
    assert fs.focus(s) is None


def test_channel_kind_resolves_colour_by_its_scale():
    v = vocab()
    assert fs.channel_kind({"channel": "length"}, v) == ("magnitude", 3)
    assert fs.channel_kind({"channel": "colour", "colour_scale": "diverging"}, v) == ("magnitude", 7)
    assert fs.channel_kind({"channel": "colour", "colour_scale": "categorical"}, v) == ("identity", 2)
    assert fs.channel_kind({"channel": "nonsense"}, v) == (None, None)


def test_figure_file_found_in_the_paper_figures_folder(tmp_path):
    p = minimal_project(tmp_path)
    s = spec()
    assert fs.figure_file(p, s) is None
    write(p / "paper/figures/fig1.pdf", "%PDF-1.4\n")
    assert fs.figure_file(p, s) == (p / "paper/figures/fig1.pdf").resolve()
    s["file"] = "elsewhere/fig1.png"
    assert fs.figure_file(p, s) is None
    write(p / "elsewhere/fig1.png", "png")
    assert fs.figure_file(p, s) == p / "elsewhere/fig1.png"
