import pytest

import idioms
from figures_fixture import VIEW_BODY, catalogue, vocab, write_idiom
from kitlib import KitError


def problems(tmp_path, body=None, **fields):
    path = write_idiom(tmp_path / "one", **({"body": body} if body else {}), **fields)
    return idioms.validate_idiom(idioms.parse_idiom(path), vocab())


def test_vocabulary_follows_marks_p9():
    v = vocab()
    ranks = {k: c["rank"] for k, c in v["channels"].items() if c["type"] in ("position", "magnitude")}
    assert ranks["position-common"] == 1 and ranks["length"] == 3 and ranks["volume"] == 10
    assert v["colour_scales"]["sequential"]["rank"] == v["channels"]["luminance"]["rank"]
    assert set(v["decks"]) == {"Layout", "Interact", "Spatial", "Spatial 2025", "Marks", "Reduce", "Data"}


def test_a_valid_idiom_has_no_problems(tmp_path):
    assert problems(tmp_path) == []


@pytest.mark.parametrize("fields, expected", [
    ({"group": "lists"}, "group"),
    ({"tasks": ["admire"]}, "tasks"),
    ({"tasks": []}, "tasks"),
    ({"medium": "static"}, "medium"),
    ({"shape": "3-keys"}, "shape"),
    ({"data": {"keys": [{"type": "nominal"}], "values": []}}, "data.keys"),
    ({"data": {"keys": [], "values": [], "colour": []}}, "unknown fields"),
    ({"marks": [{"level": 0, "mark": "point"}]}, "marks"),
    ({"channels": {"encoded": [{"channel": "glow", "carries": "v"}], "uniform": [], "varying": [],
                   "inherited": []}}, "channel"),
    ({"channels": {"encoded": [{"channel": "length", "carries": "v", "extra": 1}], "uniform": [],
                   "varying": [], "inherited": []}}, "channels"),
    ({"channels": {"encoded": [{"channel": ["hue"], "carries": "v"}], "uniform": [], "varying": [],
                   "inherited": []}}, "channel"),
    ({"data": {"keys": [], "values": [], "optional": [{"type": "categorical", "channel": ["hue"]}]}}, "optional"),
    ({"scale": {"rows": {"max": 3}, "note": None}}, "scale"),
    ({"scale": {"items": {"max": 3}}}, "note"),
    ({"see_also": [{"id": "x"}]}, "see_also"),
    ({"sources": ["Lectures p. 3"]}, "sources"),
    ({"sources": []}, "sources"),
    ({"order": 0}, "order"),
    ({"order": "first"}, "order"),
    ({"order": True}, "order"),
    ({"data": {"keys": [], "values": [{"type": "quantitative", "repeats": True}, {"type": "quantitative"}]}},
     "last entry"),
    ({"data": {"keys": [], "values": [{"type": "quantitative", "repeats": "yes"}]}}, "repeats"),
    ({"data": {"keys": [{"type": ["categorical", "ordinal"]}], "values": []}}, "data.keys"),
    ({"data": {"keys": [], "values": [], "optional": [{"type": []}]}}, "may list several"),
    ({"data": {"keys": [], "values": [], "intervals": "yes"}}, "intervals must be"),
    ({"data": {"keys": [{"type": "categorical", "repeat": True}], "values": []}}, "unknown fields: repeat"),
    ({"data": {"keys": [], "values": [{"type": "quantitative", "channel": "hue"}]}}, "unknown fields: channel"),
    ({"data": {"keys": [], "values": [], "optional": [{"type": ["categorical", "nominal"]}]}}, "may list several"),
    ({"data": {"keys": [], "values": [], "optional": [{"type": "categorical", "repeats": 1}]}}, "repeats"),
    ({"data": {"keys": [{"type": "categorical", "repeats": True}, {"type": "ordinal"}], "values": []}}, "last entry"),
])
def test_invalid_fields_are_named(tmp_path, fields, expected):
    found = problems(tmp_path, **fields)
    assert found and any(expected in p for p in found), found


def test_id_must_match_the_file_name(tmp_path):
    path = write_idiom(tmp_path / "one", id="fixture-bars")
    renamed = path.rename(path.with_name("other.md"))
    assert any("id" in p for p in idioms.validate_idiom(idioms.parse_idiom(renamed), vocab()))


def test_body_needs_its_sections_no_quotes_and_known_decks(tmp_path):
    assert any("Arrange" in p for p in problems(tmp_path, body="## Helps\nx\n\n## Hides\ny\n"))
    quoted = "## Helps\nShe calls it “good”.\n\n## Hides\nx\n\n## Arrange\ny\n"
    assert any("quotation" in p for p in problems(tmp_path, body=quoted))
    straight = '## Helps\nA "quoted" word.\n\n## Hides\nx\n\n## Arrange\ny\n'
    assert any("quotation" in p for p in problems(tmp_path, body=straight))
    unknown = "## Helps\nCompares (Lectures p. 3).\n\n## Hides\nx\n\n## Arrange\ny\n"
    assert any("Lectures" in p for p in problems(tmp_path, body=unknown))


def test_kit_and_own_idioms_may_have_no_sources(tmp_path):
    assert problems(tmp_path, origin="kit", sources=[]) == []
    assert problems(tmp_path, origin="own", sources=[]) == []


def test_view_idioms_have_changes_and_views_not_channels(tmp_path):
    ok = dict(form="view", channels=None, marks=None, changes="the order", fixed="the encoding", shape="any-data",
              data={"keys": [], "values": []})
    assert problems(tmp_path, body=VIEW_BODY, **ok) == []
    assert any("channels: null" in p for p in problems(tmp_path, body=VIEW_BODY, **{**ok, "channels": {}}))
    assert any("changes" in p for p in problems(tmp_path, body=VIEW_BODY, **{**ok, "changes": ""}))


def test_catalogue_order_override_and_additions(tmp_path):
    kit, mine = tmp_path / "kit", tmp_path / "mine"
    write_idiom(kit, id="zeta-bars")
    write_idiom(kit, id="alpha-map", group="spatial", shape="geographic")
    write_idiom(kit, id="alpha-bars")
    write_idiom(mine, id="zeta-bars", name="My zeta bars")
    write_idiom(mine, id="added-bars")
    cat = idioms.load_catalogue(vocab(), kit_dir=kit, personal=mine)
    assert list(cat) == ["alpha-bars", "zeta-bars", "alpha-map", "added-bars"]
    assert cat["zeta-bars"]["name"] == "My zeta bars" and cat["zeta-bars"]["_source"] == "personal"


def test_catalogue_stops_on_an_invalid_file_or_unknown_see_also(tmp_path):
    kit = tmp_path / "kit"
    write_idiom(kit, id="good-bars")
    write_idiom(tmp_path / "mine", id="bad-bars", group="nowhere")
    with pytest.raises(KitError, match="bad-bars.md"):
        idioms.load_catalogue(vocab(), kit_dir=kit, personal=tmp_path / "mine")
    write_idiom(tmp_path / "kit2", id="lonely-bars", see_also=[{"id": "missing", "when": "never"}])
    with pytest.raises(KitError, match="missing"):
        idioms.load_catalogue(vocab(), kit_dir=tmp_path / "kit2", personal=tmp_path / "none")


def test_first_sentence_skips_page_abbreviations():
    text = "Bars mislead without zero (Layout p. 25). Exceptions exist (Layout p. 26)."
    assert idioms.first_sentence(text) == "Bars mislead without zero (Layout p. 25)."
    assert idioms.first_sentence("") == ""


def test_fixture_catalogue_helper(tmp_path):
    cat = catalogue(tmp_path, {"id": "one-bars"}, {"id": "two-bars"})
    assert list(cat) == ["one-bars", "two-bars"]


def test_the_kit_catalogue_is_valid(tmp_path):
    cat = idioms.load_catalogue(vocab(), personal=tmp_path / "none")
    assert len(cat) == 52
    orders = [i.get("order") for i in cat.values()]
    assert None not in orders and len(set(orders)) == len(orders)
    assert list(cat)[:3] == ["line-chart", "bar-chart", "interval-plot"]
    assert cat["interval-plot"]["origin"] == "kit" and cat["line-chart"]["origin"] == "munzner"
    assert {i["origin"] for i in cat.values()} == {"munzner", "kit"}
    assert {i for i, d in cat.items() if d["data"].get("intervals")} == {"interval-plot", "boxplot",
                                                                         "specification-curve"}
    assert cat["dot-density-map"]["channels"]["encoded"][0]["channel"] == "density"


def test_vocabulary_has_trend_and_an_unranked_density_channel():
    v = vocab()
    assert "trend" in v["tasks"] and "change-over-" + "time" not in v["tasks"]      # split: Step 2's sed skips it
    assert v["channels"]["density"]["type"] == "magnitude" and v["channels"]["density"]["rank"] is None


def test_order_repeats_type_lists_and_intervals_are_valid(tmp_path):
    data = {"keys": [], "values": [{"type": "quantitative"}, {"type": "quantitative", "repeats": True}],
            "optional": [{"type": ["categorical", "quantitative"], "channel": "colour"},
                         {"type": "categorical", "channel": "position-common", "repeats": True}],
            "intervals": True}
    assert problems(tmp_path, data=data, order=30) == []


def test_slot_types():
    assert idioms.slot_types({"type": "ordinal"}) == ["ordinal"]
    assert idioms.slot_types({"type": ["categorical", "quantitative"]}) == ["categorical", "quantitative"]


def test_catalogue_sorts_by_order_first(tmp_path):
    kit, mine = tmp_path / "kit", tmp_path / "mine"
    write_idiom(kit, id="plain-map", group="spatial", shape="geographic", order=10)
    write_idiom(kit, id="fancy-bars", order=20)
    write_idiom(kit, id="loose-bars")
    write_idiom(mine, id="my-bars", order=15)
    write_idiom(mine, id="extra-bars")
    cat = idioms.load_catalogue(vocab(), kit_dir=kit, personal=mine)
    assert list(cat) == ["plain-map", "my-bars", "fancy-bars", "loose-bars", "extra-bars"]


def test_equal_order_puts_the_kit_idiom_first(tmp_path):
    write_idiom(tmp_path / "kit", id="kit-bars", order=10)
    write_idiom(tmp_path / "mine", id="a-bars", order=10)
    cat = idioms.load_catalogue(vocab(), kit_dir=tmp_path / "kit", personal=tmp_path / "mine")
    assert list(cat) == ["kit-bars", "a-bars"]
