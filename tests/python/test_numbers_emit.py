import csv
import math

import pytest

from numbers_emit import NumbersEmitError, emit_numbers


def entry(**kw):
    return {"name": "coverageMain", "value": 0.9412, "format": "%.2f", "src": "analysis/s.csv", **kw}


@pytest.fixture
def out(tmp_path, monkeypatch):
    path = tmp_path / "entries.csv"
    monkeypatch.setenv("KIT_NUMBERS_OUT", str(path))
    return path


def rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_writes_formatted_rows(out):
    emit_numbers([entry(), entry(name="labelText", value='a, "b"', format="%s")])
    assert rows(out) == [{"name": "coverageMain", "value": "0.94", "src": "analysis/s.csv"},
                         {"name": "labelText", "value": 'a, "b"', "src": "analysis/s.csv"}]


def test_empty_list_writes_header_only(out):
    emit_numbers([])
    assert out.read_text(encoding="utf-8").splitlines() == ["name,value,src"]


def test_unset_env_refused(monkeypatch):
    monkeypatch.delenv("KIT_NUMBERS_OUT", raising=False)
    with pytest.raises(NumbersEmitError, match="run make_numbers through numbers_build.py"):
        emit_numbers([entry()])


def test_second_call_refused(out):
    emit_numbers([])
    with pytest.raises(NumbersEmitError, match="called twice"):
        emit_numbers([])


def test_missing_field_refused(out):
    e = entry()
    del e["src"]
    with pytest.raises(NumbersEmitError, match="lacks"):
        emit_numbers([e])
    assert not out.exists()


@pytest.mark.parametrize("value", [math.nan, math.inf, True, None, [1, 2]])
def test_bad_value_refused(out, value):
    with pytest.raises(NumbersEmitError, match="single finite number or a string"):
        emit_numbers([entry(value=value)])


def test_bad_format_refused(out):
    with pytest.raises(NumbersEmitError, match="format '%d'"):
        emit_numbers([entry(value="x", format="%d")])


@pytest.mark.parametrize("fmt", ["%d", "%ld", "%hd", "%Li"])
def test_int_format_needs_whole_number(out, fmt):
    with pytest.raises(NumbersEmitError, match="needs a whole number"):
        emit_numbers([entry(value=0.94, format=fmt)])


@pytest.mark.parametrize("value", [3, 3.0])
def test_int_format_whole_numbers(out, value):
    emit_numbers([entry(value=value, format="%d")])
    assert rows(out)[0]["value"] == "3"


@pytest.mark.parametrize("field", ["name", "src"])
def test_none_text_field_refused(out, field):
    with pytest.raises(NumbersEmitError, match="must be a non-empty string"):
        emit_numbers([entry(**{field: None})])


def test_non_string_format_refused(out):
    with pytest.raises(NumbersEmitError, match="must be a non-empty string"):
        emit_numbers([entry(format=5)])


@pytest.mark.parametrize("fmt", ["abc", "%%"])
def test_format_needs_one_conversion(out, fmt):
    with pytest.raises(NumbersEmitError, match="exactly one conversion"):
        emit_numbers([entry(format=fmt)])


def test_percent_literal_allowed(out):
    emit_numbers([entry(value=12.34, format="%.1f%%")])
    assert rows(out)[0]["value"] == "12.3%"


def test_non_dict_entry_refused(out):
    with pytest.raises(NumbersEmitError, match="must be a dict"):
        emit_numbers(["x"])


def test_entries_not_list_refused(out):
    with pytest.raises(NumbersEmitError, match="list of dicts"):
        emit_numbers({"name": "a"})


def test_huge_int_refused(out):
    with pytest.raises(NumbersEmitError):
        emit_numbers([entry(value=10**400)])
