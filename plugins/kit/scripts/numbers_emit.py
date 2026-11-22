"""Emit a paper's numbers for numbers_build.py (research-kit languages spec §5.1).

make_numbers.py loads this file by path and calls emit_numbers(entries) once. Standard library only,
so the project's Python environment needs nothing extra.
"""
from __future__ import annotations

import csv
import math
import numbers
import os
import re
from pathlib import Path

FIELDS = ("name", "value", "format", "src")
CONV_RE = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[hlL]?([a-zA-Z%])")


class NumbersEmitError(Exception):
    pass


def _formatted(k: int, e) -> tuple[str, str, str]:
    if not isinstance(e, dict):
        raise NumbersEmitError(f"entry {k} must be a dict with keys {', '.join(FIELDS)}")
    missing = [f for f in FIELDS if f not in e]
    if missing:
        raise NumbersEmitError(f"entry {k} lacks {', '.join(missing)}")
    for f in ("name", "format", "src"):
        if not isinstance(e[f], str) or not e[f]:
            raise NumbersEmitError(f"entry {k}: {f} must be a non-empty string, got {e[f]!r}")
    name, fmt = e["name"], e["format"]
    v = e["value"]
    try:
        ok = isinstance(v, str) or (isinstance(v, numbers.Real) and not isinstance(v, bool) and math.isfinite(v))
    except OverflowError:
        ok = False
    if not ok:
        raise NumbersEmitError(f"value for {name!r} must be a single finite number or a string, got {v!r}")
    convs = [c for c in CONV_RE.findall(fmt) if c != "%"]
    if len(convs) != 1:
        raise NumbersEmitError(f"format {fmt!r} for {name!r} must contain exactly one conversion such as %.2f, %d or %s")
    if convs[0] in "diu" and not isinstance(v, (str, numbers.Integral)) and not float(v).is_integer():
        raise NumbersEmitError(f"format {fmt!r} for {name!r} needs a whole number, got {v!r}; round it or use %.0f")
    try:
        text = fmt % v
    except (TypeError, ValueError, OverflowError) as err:
        raise NumbersEmitError(f"format {fmt!r} for {name!r} failed: {err}") from None
    return name, text, e["src"]


def emit_numbers(entries) -> None:
    out = os.environ.get("KIT_NUMBERS_OUT", "")
    if not out:
        raise NumbersEmitError("KIT_NUMBERS_OUT is not set: run make_numbers through numbers_build.py")
    path = Path(out)
    if path.exists():
        raise NumbersEmitError(f"{path} already exists: emit_numbers was called twice in one run")
    if not isinstance(entries, (list, tuple)):
        raise NumbersEmitError("entries must be a list of dicts")
    rows = [_formatted(k, e) for k, e in enumerate(entries, start=1)]
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("name", "value", "src"))
        w.writerows(rows)
    os.replace(tmp, path)
