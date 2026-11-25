"""The project's parameters, written by research-kit (code spec section 2).

Code never types a number, date or path: it reads them from analysis/params.yml (the pipeline's,
approved) or analysis/explore/params.yml (quick questions) with param("name"), after putting this file's
folder on sys.path and `from params import param`. The files are found from this file's own place, so a
script may run from any folder; a missing analysis/params.yml is an error.
"""
import re
from pathlib import Path

_ENTRY = re.compile(r"([a-z][a-z0-9_]*):[ ]?(.*)")
_ITEM = re.compile(r"'(?:[^']|'')*'|[^,\s][^,]*")


def _value(text):
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    if text.startswith("'"):
        return text[1:-1].replace("''", "'")
    if text.startswith("["):
        return [_value(item) for item in _ITEM.findall(text[1:-1])]
    return float(text) if any(c in text for c in ".eE") else int(text)


def _read(path, required):
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"{path}: analysis/params.yml is missing; run the kit's scaffold.py add-params")
        return []
    found = (_ENTRY.fullmatch(line) for line in path.read_text(encoding="utf-8-sig").splitlines())
    return [(m.group(1), _value(m.group(2))) for m in found if m]


_HERE = Path(__file__).resolve().parent             # the project's analysis/ folder
_ENTRIES = _read(_HERE / "params.yml", True) + _read(_HERE / "explore" / "params.yml", False)  # literal: the files
_PARAMS = dict(_ENTRIES)
_TWICE = sorted({name for name, _ in _ENTRIES if [n for n, _ in _ENTRIES].count(name) > 1})
if _TWICE:
    raise ValueError("parameters defined twice in analysis/params.yml and analysis/explore/params.yml: "
                     + ", ".join(_TWICE))


def param(name):
    """The value of a parameter; an unknown name is an error, never a silent None."""
    if name not in _PARAMS:
        raise KeyError(f"no parameter {name!r} in analysis/params.yml or analysis/explore/params.yml")
    return _PARAMS[name]


def param_path(name):
    """A path parameter, which is relative to the project root, as a full path that works from any folder."""
    value = param(name)
    if not isinstance(value, str):
        raise TypeError(f"parameter {name!r} is not one path: {value!r}")
    path = Path(value).expanduser()
    return path if path.is_absolute() else _HERE.parent / path
