import os
from pathlib import Path

import pytest

import figures
import idioms
from build_fixture import minimal_project, write
from figures_fixture import write_idiom


def personal_idioms() -> Path:
    return Path(os.environ["KIT_PERSONAL_DIR"]) / "idioms"


SPEC = """figure: fig1
script: analysis/fig1.R
title: Estimate by group
what:
  items: one estimate per group
  n_items: 4
  keys: [{name: group, type: categorical, levels: 4}]
  values: [{name: estimate, type: quantitative}]
why: {task: compare-values, message: Group C is highest.}
how:
  idiom: fixture-bars
  encode:
    group: [{channel: position-common, axis: x}]
    estimate: [{channel: length}]
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(idioms, "KIT_IDIOMS", tmp_path / "no-kit-idioms")   # fixture idioms only
    write_idiom(personal_idioms(), id="fixture-bars")
    write_idiom(personal_idioms(), id="fixture-line", tasks=["trend"], shape="1-key",
                data={"keys": [{"type": "ordinal"}], "values": [{"type": "quantitative"}]})
    write_idiom(personal_idioms(), id="fixture-map", group="spatial", shape="geographic", tasks=["spatial-pattern"])
    write_idiom(personal_idioms(), id="fixture-brush", medium=["interactive"], tasks=["trend"])
    return minimal_project(tmp_path)


def test_candidates_order_and_fill(project, capsys):
    assert figures.main(["candidates", "--project", str(project), "--task", "trend",
                         "--shape", "1-key", "--key-types", "ordinal"]) == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith("fixture-")]
    assert lines[0].startswith("fixture-line: ")
    assert any(l.startswith("fixture-bars: ") and "doesn't list this task" in l for l in lines)
    assert not any(l.startswith(("fixture-map", "fixture-brush")) for l in lines)
    assert figures.main(["candidates", "--project", str(project), "--task", "trend",
                         "--medium", "any"]) == 0
    assert "fixture-brush: " in capsys.readouterr().out


def test_candidates_rejects_unknown_terms(project, capsys):
    assert figures.main(["candidates", "--project", str(project), "--task", "admire"]) == 2
    assert "admire" in capsys.readouterr().err


def test_candidates_label_kit_and_own_idioms(project, capsys):
    write_idiom(personal_idioms(), id="fixture-kit", origin="kit", sources=[])
    write_idiom(personal_idioms(), id="fixture-own", origin="own", sources=[])
    assert figures.main(["candidates", "--project", str(project), "--task", "compare-values"]) == 0
    lines = {l.split(":")[0]: l for l in capsys.readouterr().out.splitlines()}
    assert "kit idiom" in lines["fixture-kit"] and "your idiom" not in lines["fixture-kit"]
    assert "your idiom" in lines["fixture-own"] and "kit idiom" not in lines["fixture-own"]
    assert "kit idiom" not in lines["fixture-bars"] and "your idiom" not in lines["fixture-bars"]


def test_check_draft_and_exit_codes(project, capsys):
    write(project / "notes/figures/fig1.yml", SPEC)
    assert figures.main(["check", "--project", str(project), "--draft"]) == 0
    assert "figures: 1 spec, 0 errors, 0 warnings, 0 accepted" in capsys.readouterr().out
    assert figures.main(["check", "--project", str(project)]) == 1
    out = capsys.readouterr().out
    assert "fig1: error spec: script not found" in out


def test_check_reports_unreadable_specs_and_panels(project, capsys):
    write(project / "notes/figures/broken.yml", "figure: [oops\n")
    write(project / "notes/figures/combo/A.yml", SPEC.replace("figure: fig1", "figure: combo\npanel: A"))
    assert figures.main(["check", "--project", str(project), "--draft"]) == 1
    out = capsys.readouterr().out
    assert "broken: error spec: cannot read broken.yml" in out
    assert "combo/A" not in out                                # the panel is clean
    assert figures.main(["check", "--project", str(project), "--draft", "combo"]) == 0


def test_check_unknown_figure_and_bad_catalogue(project, capsys):
    assert figures.main(["check", "--project", str(project), "nothing"]) == 2
    assert "no spec for nothing" in capsys.readouterr().err
    write_idiom(personal_idioms(), id="broken-bars", group="nowhere")
    assert figures.main(["check", "--project", str(project), "--draft"]) == 2
    assert "broken-bars.md" in capsys.readouterr().err


def test_candidates_say_when_shape_or_types_do_not_fit(project, capsys):
    assert figures.main(["candidates", "--project", str(project), "--task", "trend",
                         "--shape", "2-keys", "--key-types", "categorical"]) == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("fixture-line"))
    assert "shape differs" in line and "types don't fit" in line
    assert figures.main(["candidates", "--project", str(project), "--task", "relationship", "--medium", "any"]) == 0
    assert "no idiom lists relationship" in capsys.readouterr().out


def test_panel_specs_need_a_panel_and_yaml_counts(project, capsys):
    write(project / "notes/figures/combo/A.yml", SPEC.replace("figure: fig1", "figure: combo"))
    assert figures.main(["check", "--project", str(project), "--draft"]) == 1
    assert "combo: error spec: a spec in notes/figures/combo/ needs a panel field" in capsys.readouterr().out
    write(project / "notes/figures/other.yaml", SPEC.replace("figure: fig1", "figure: other"))
    assert figures.main(["check", "--project", str(project), "--draft", "other"]) == 0


def test_check_with_no_specs(project, capsys):
    assert figures.main(["check", "--project", str(project)]) == 0
    assert "no figure specs" in capsys.readouterr().out


def test_candidates_on_the_kit_catalogue(tmp_path, capsys):
    p = minimal_project(tmp_path)

    def first(*args: str) -> list[str]:
        assert figures.main(["candidates", "--project", str(p), *args]) == 0
        return [l.split(":")[0] for l in capsys.readouterr().out.splitlines()]
    assert first("--task", "compare-values", "--shape", "1-key", "--key-types", "categorical")[:3] == \
        ["bar-chart", "interval-plot", "dot-plot"]
    assert first("--task", "trend", "--shape", "1-key", "--key-types", "ordinal")[0] == "line-chart"
    assert first("--task", "trend", "--shape", "1-key", "--key-types", "quantitative")[0] == "line-chart"
    assert first("--task", "trend", "--shape", "1-key", "--key-types", "ordinal", "--intervals")[0] == \
        "interval-plot"
    assert first("--task", "spatial-pattern", "--shape", "geographic")[0] == "choropleth-map"
    assert first("--task", "distribution", "--shape", "1-key", "--key-types", "categorical",
                 "--value-types", "quantitative")[0] == "boxplot"


def test_candidates_intervals_put_interval_idioms_first(project, capsys):
    write_idiom(personal_idioms(), id="fixture-intervals", tasks=["trend"],
                data={"keys": [{"type": "categorical"}], "values": [{"type": "quantitative"}], "intervals": True})
    args = ["candidates", "--project", str(project), "--task", "trend", "--shape", "1-key", "--key-types", "ordinal"]
    assert figures.main(args) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("fixture-line: ")
    assert figures.main(args + ["--intervals"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("fixture-intervals: ") and "draws no intervals" not in lines[0]
    assert any(l.startswith("fixture-line: ") and "draws no intervals" in l for l in lines)


def test_candidates_shape_outranks_intervals(project, capsys):
    write_idiom(personal_idioms(), id="fixture-wide-intervals", tasks=["trend"], shape="2-keys",
                data={"keys": [{"type": "categorical"}, {"type": "categorical"}],
                      "values": [{"type": "quantitative"}], "intervals": True})
    assert figures.main(["candidates", "--project", str(project), "--task", "trend", "--shape", "1-key",
                         "--intervals"]) == 0
    ids = [l.split(":")[0] for l in capsys.readouterr().out.splitlines()]
    assert ids.index("fixture-line") < ids.index("fixture-wide-intervals")
