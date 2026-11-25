import datetime as dt
from pathlib import Path

import pytest

import figure_checks as fc
from build_fixture import minimal_project, write
from figures_fixture import catalogue, spec, vocab

LINE = {"id": "fixture-line", "tasks": ["trend"], "data": {"keys": [{"type": "ordinal"}],
        "values": [{"type": "quantitative"}], "optional": [{"type": "categorical", "channel": "hue"}]},
        "see_also": [{"id": "fixture-bars", "when": "categorical key"}]}
STACK = {"id": "fixture-stack", "scale": {"key_levels": {"max": 12}, "items": {"min": 3}, "note": "about a dozen"},
         "channels": {"encoded": [{"channel": "length", "carries": "value"}], "uniform": [],
                      "varying": [{"channel": "position-common", "where": "upper segments"}], "inherited": []}}


@pytest.fixture
def cat(tmp_path):
    return catalogue(tmp_path, {}, LINE, STACK)


def ctx(cat, idiom="fixture-bars", project=Path("."), draft=True):
    return fc.Context(cat.get(idiom), cat, vocab(), project, draft)


def found(findings, check=None):
    return [(f.check, f.severity, f.attribute) for f in findings if check is None or f.check == check]


def test_a_good_spec_has_no_findings(cat):
    assert fc.run_checks(spec(), ctx(cat)) == []


@pytest.mark.parametrize("change, expected", [
    (lambda s: s.pop("why"), "missing field: why"),
    (lambda s: s["what"]["keys"][0].update(type="nominal"), "type"),
    (lambda s: s["how"].update(idiom="no-such"), "unknown idiom"),
    (lambda s: s["how"]["encode"].update(group=[{"channel": "colour"}]), "colour_scale"),
    (lambda s: s["how"]["encode"].update(nobody=[{"channel": "hue"}]), "unknown attribute"),
    (lambda s: s["how"].update(facet={"by": "group"}), "role: facet"),
    (lambda s: s["how"].update(reference=[{"kind": "line", "axis": "y", "at": 0}]), "meaning"),
    (lambda s: s["how"].update(reference=[{"kind": "band", "axis": "x", "from": 1, "meaning": "m"}]), "from and to"),
    (lambda s: s["why"].update(task="admire"), "why.task"),
    (lambda s: s["how"]["encode"].update(group=[{"channel": ["hue", "shape"]}]), "not in the vocabulary"),
    (lambda s: s["how"]["encode"].update(group=[{"channel": "colour", "colour_scale": ["x"]}]), "colour_scale"),
    (lambda s: s.update(file=5), "file must be"),
    (lambda s: s.update(title=""), "title must be"),
    (lambda s: s["how"].update(reference=[{"kind": "line", "axis": "y", "at": "banana", "meaning": "m"}]), "date"),
    (lambda s: s["how"].update(reference=[{"kind": "line", "axis": "y", "at": "2020-13", "meaning": "m"}]), "date"),
    (lambda s: s["how"].update(reference=[{"kind": "line", "axis": "y", "at": float("nan"), "meaning": "m"}]), "date"),
    (lambda s: s.update(panel=["a"]), "panel must be"),
    (lambda s: s.update(figure="/abs/effect_by_year"), "file name"),
    (lambda s: s.update(figure="effect**"), "file name"),
    (lambda s: s["what"].update(spatial="planets"), "spatial"),
    (lambda s: s["how"]["encode"]["group"][0].update(axis="z"), "axis"),
])
def test_spec_errors_stop_the_other_checks(cat, change, expected):
    s = spec()
    change(s)
    out = fc.run_checks(s, ctx(cat))
    assert out and all(f.check == "spec" and f.severity == "error" for f in out)
    assert any(expected in f.message for f in out), [f.message for f in out]


def test_facet_by_must_be_a_key_and_dates_are_positions(cat):
    s = spec()
    s["what"]["values"].append({"name": "panel", "type": "categorical", "role": "facet"})
    s["how"]["facet"] = {"by": "panel"}
    assert any("a key with role: facet" in f.message for f in fc.check_spec(s, ctx(cat)))
    s = spec()
    s["how"]["reference"] = [{"kind": "line", "axis": "x", "at": dt.date(2020, 1, 1), "meaning": "reform"},
                             {"kind": "band", "axis": "x", "from": "2019-06", "to": 2021, "meaning": "rollout"}]
    assert fc.check_spec(s, ctx(cat)) == []


def test_draft_skips_files_and_a_full_check_needs_them(cat, tmp_path):
    p = minimal_project(tmp_path)
    assert fc.check_spec(spec(), ctx(cat, project=p, draft=True)) == []
    msgs = [f.message for f in fc.check_spec(spec(), ctx(cat, project=p, draft=False))]
    assert any("script not found" in m for m in msgs) and any("figure file not found" in m for m in msgs)
    write(p / "analysis/fig1.R", "# plot\n")
    write(p / "paper/figures/fig1.pdf", "%PDF\n")
    assert fc.check_spec(spec(), ctx(cat, project=p, draft=False)) == []


def test_data_fit(cat):
    s = spec()
    s["what"]["keys"] = []
    assert found(fc.check_data_fit(s, ctx(cat))) == [("data-fit", "error", None)]
    s = spec()
    s["what"]["keys"][0]["type"] = "quantitative"            # chains to categorical: no finding
    assert fc.check_data_fit(s, ctx(cat)) == []
    s["what"]["values"][0]["type"] = "categorical"            # categorical where quantitative is expected
    assert found(fc.check_data_fit(s, ctx(cat))) == [("data-fit", "warning", "estimate")]
    s = spec()
    s["what"]["values"] += [{"name": "low", "type": "quantitative", "role": "interval"},
                            {"name": "other", "type": "quantitative"}]
    assert found(fc.check_data_fit(s, ctx(cat))) == [("data-fit", "warning", "other")]
    s = spec(how={"idiom": "fixture-line", "encode": {"series": [{"channel": "colour", "colour_scale": "categorical"}]}})
    s["what"]["keys"] = [{"name": "year", "type": "ordinal"}, {"name": "series", "type": "categorical"}]
    assert fc.check_data_fit(s, ctx(cat, "fixture-line")) == []      # series fills the optional hue slot
    s["how"]["encode"]["series"] = [{"channel": "shape"}]            # not on the slot's channel
    assert found(fc.check_data_fit(s, ctx(cat, "fixture-line"))) == [("data-fit", "warning", "series")]
    s = spec(how={"idiom": "fixture-line", "encode": {"low": [{"channel": "hue"}]}})
    s["what"]["keys"] = [{"name": "year", "type": "ordinal"}]
    s["what"]["values"].append({"name": "low", "type": "quantitative"})  # a bound missing its role
    assert found(fc.check_data_fit(s, ctx(cat, "fixture-line"))) == [("data-fit", "warning", "low")]


def test_task_names_idioms_that_serve_it(cat):
    s = spec()
    s["why"]["task"] = "trend"
    out = fc.check_task(s, ctx(cat))
    assert found(out) == [("task", "warning", None)] and "fixture-line" in out[0].message


@pytest.mark.parametrize("attr, entry, focus, expected", [
    ("group", {"channel": "length"}, None, [("expressiveness", "error", "group")]),
    ("group", {"channel": "position-common"}, None, []),
    ("group", {"channel": "hue"}, None, []),
    ("estimate", {"channel": "shape"}, "group", [("expressiveness", "warning", "estimate")]),
    ("estimate", {"channel": "shape"}, None, [("expressiveness", "error", "estimate")]),
    ("estimate", {"channel": "colour", "colour_scale": "diverging"}, None, []),
    ("group", {"channel": "colour", "colour_scale": "sequential"}, None, [("expressiveness", "error", "group")]),
])
def test_expressiveness(cat, attr, entry, focus, expected):
    s = spec()
    s["how"]["encode"][attr] = [entry]
    if focus:
        s["why"]["focus"] = focus
    assert found(fc.check_expressiveness(s, ctx(cat))) == expected


def test_redundant_identity_channels_on_a_categorical_key_pass(cat):
    s = spec()
    s["how"]["encode"]["group"] = [{"channel": "hue"}, {"channel": "shape"}]
    assert fc.check_expressiveness(s, ctx(cat)) == []


def test_effectiveness(cat):
    s = spec()
    s["what"]["values"].append({"name": "share", "type": "quantitative"})
    s["how"]["encode"]["share"] = [{"channel": "position-common"}]
    out = fc.check_effectiveness(s, ctx(cat))                # focus estimate on length (3), share on position (1)
    assert found(out) == [("effectiveness", "warning", "estimate")] and "share" in out[0].message
    s["why"]["focus"] = "share"
    assert fc.check_effectiveness(s, ctx(cat)) == []
    s["why"]["focus"] = {"derived": "gap between the two"}
    assert fc.check_effectiveness(s, ctx(cat)) == []
    s = spec()
    s["how"]["encode"]["estimate"] = [{"channel": "linetype"}]
    assert found(fc.check_effectiveness(s, ctx(cat))) == [("effectiveness", "warning", "estimate")]
    s = spec()
    s["why"]["focus"] = "group"                     # categorical focus on hue: not this check's business
    s["how"]["encode"]["group"] = [{"channel": "hue"}]
    assert fc.check_effectiveness(s, ctx(cat)) == []


def test_scale(cat):
    s = spec(how={"idiom": "fixture-stack", "encode": {"group": [{"channel": "position-common"}],
                                                       "estimate": [{"channel": "length"}]}})
    assert fc.check_scale(s, ctx(cat, "fixture-stack")) == []
    s["what"]["keys"][0]["levels"] = 20
    s["what"]["n_items"] = 2
    msgs = [f.message for f in fc.check_scale(s, ctx(cat, "fixture-stack"))]
    assert len(msgs) == 2 and any("key_levels 20" in m and "about a dozen" in m for m in msgs)


def test_accepted_warnings_match_check_and_attribute(cat):
    s = spec()
    s["how"]["encode"]["estimate"] = [{"channel": "shape"}]
    s["why"]["focus"] = "group"
    s["accepted"] = [{"check": "expressiveness", "attribute": "estimate", "reason": "labelled directly"}]
    assert found(fc.run_checks(s, ctx(cat)), "expressiveness") == [("expressiveness", "accepted", "estimate")]
    s["accepted"] = [{"check": "expressiveness", "attribute": "other", "reason": "x"}]
    assert found(fc.run_checks(s, ctx(cat)), "expressiveness") == [("expressiveness", "warning", "estimate")]
    s["why"].pop("focus")                                     # now an error, which can't be accepted
    s["accepted"] = [{"check": "expressiveness", "reason": "x"}]
    assert found(fc.run_checks(s, ctx(cat)), "expressiveness") == [("expressiveness", "error", "estimate")]


def test_no_idiom_still_runs_the_idiom_free_checks(cat):
    s = spec(how={"idiom": "none", "encode": {"group": [{"channel": "length"}],
                                              "estimate": [{"channel": "position-common"}]}})
    assert found(fc.run_checks(s, ctx(cat, None))) == [("expressiveness", "error", "group")]


def test_coefficient_plot_with_interval_role_passes(cat):
    s = spec()
    s["what"]["values"] += [{"name": "low", "type": "quantitative", "role": "interval"},
                            {"name": "high", "type": "quantitative", "role": "interval"}]
    s["how"]["encode"].update(estimate=[{"channel": "position-common", "axis": "y"}],
                              low=[{"channel": "position-common", "axis": "y"}],
                              high=[{"channel": "position-common", "axis": "y"}])
    s["how"]["reference"] = [{"kind": "line", "axis": "y", "at": 0, "meaning": "no effect"}]
    assert fc.run_checks(s, ctx(cat)) == []


MATRIX = {"id": "fixture-matrix", "shape": "0-keys", "tasks": ["relationship"],
          "data": {"keys": [], "values": [{"type": "quantitative"}, {"type": "quantitative", "repeats": True}],
                   "optional": [{"type": ["categorical", "quantitative"], "channel": "colour"},
                                {"type": "categorical", "channel": "shape", "repeats": True}]}}


def test_data_fit_repeats_type_lists_and_colour_slots(tmp_path):
    cat = catalogue(tmp_path, {}, MATRIX)
    s = spec(how={"idiom": "fixture-matrix", "encode": {}})
    s["what"]["keys"] = []
    s["what"]["values"] = [{"name": n, "type": "quantitative"} for n in ("a", "b", "c", "d")]
    assert fc.check_data_fit(s, ctx(cat, "fixture-matrix")) == []        # the last value slot repeats
    s["what"]["keys"] = [{"name": "share", "type": "quantitative"}]
    s["how"]["encode"] = {"share": [{"channel": "colour", "colour_scale": "sequential"}]}
    assert fc.check_data_fit(s, ctx(cat, "fixture-matrix")) == []        # quantitative fits the colour slot
    s["what"]["keys"] += [{"name": "region", "type": "categorical"}, {"name": "sector", "type": "categorical"}]
    s["how"]["encode"].update(region=[{"channel": "shape"}], sector=[{"channel": "shape"}])
    assert fc.check_data_fit(s, ctx(cat, "fixture-matrix")) == []        # a repeating slot takes both
    s["what"]["keys"].append({"name": "party", "type": "categorical"})
    s["how"]["encode"]["party"] = [{"channel": "hue"}]
    assert found(fc.check_data_fit(s, ctx(cat, "fixture-matrix"))) == [("data-fit", "warning", "party")]


def test_data_fit_repeating_and_channel_slots_still_warn(tmp_path):
    cat = catalogue(tmp_path, {}, MATRIX, LINE)
    s = spec(how={"idiom": "fixture-matrix", "encode": {"grade": [{"channel": "position-common"}]}})
    s["what"]["keys"] = []
    s["what"]["values"] = [{"name": "a", "type": "quantitative"}, {"name": "b", "type": "quantitative"},
                           {"name": "grade", "type": "categorical"}]
    assert found(fc.check_data_fit(s, ctx(cat, "fixture-matrix"))) == [("data-fit", "warning", "grade")]
    s = spec(how={"idiom": "fixture-line",
                  "encode": {"series": [{"channel": "colour", "colour_scale": "sequential"}]}})
    s["what"]["keys"] = [{"name": "year", "type": "ordinal"}, {"name": "series", "type": "categorical"}]
    assert found(fc.check_data_fit(s, ctx(cat, "fixture-line"))) == [("data-fit", "warning", "series")]
