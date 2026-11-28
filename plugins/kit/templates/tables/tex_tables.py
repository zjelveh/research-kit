"""The paper's LaTeX tables, written by research-kit's table writer (table writer spec); the project owns this
file and may edit it. A driver builds the paper's style once and passes it to every function:

    style = table_style(param)                        # the table_* settings in analysis/params.yml
    small = table_style(param, size="scriptsize")     # one setting overridden, for one table

Every number goes through tex_number(), so a negative prints with a real minus and a value that rounds to zero
without a sign; stars and their legend come from the same thresholds. Standard library only, so the paper's
replication code needs nothing else to run it.
"""
from __future__ import annotations

import dataclasses
import math
import sys
from pathlib import Path

# The paper's table settings, entries of analysis/params.yml; the style's fields drop the table_ prefix.
TABLE_SETTINGS = (
    "table_star_thresholds", "table_star_markers", "table_decimals", "table_thousands", "table_se_brackets",
    "table_interval_brackets", "table_interval_sep", "table_p_decimals", "table_p_floor", "table_p_leading_zero",
    "table_missing", "table_size", "table_placement", "table_caption_period", "table_notes_lead",
    "table_notes_size", "table_notes_width", "table_notes_skip", "table_tabcolsep", "table_arraystretch",
)
MARKERS = ("*", "**", "***", "\\dagger", "\\ddagger")   # the symbols the paper's table check reads
MAX_DECIMALS = 6  # literal: the widest a number, p-value or threshold is printed
GROUP = 3  # literal: digits between thousands separators
MINUS = "$-$"
_WORDS = ("thousands", "interval_sep", "missing", "size", "placement", "notes_lead", "notes_size", "notes_width",
          "notes_skip", "tabcolsep", "arraystretch")
_PAIRS = ("se_brackets", "interval_brackets")


@dataclasses.dataclass(frozen=True)
class TableStyle:
    """The paper's table style: one field per table_* setting, named without the prefix."""
    star_thresholds: tuple
    star_markers: tuple
    decimals: int
    thousands: str
    se_brackets: tuple
    interval_brackets: tuple
    interval_sep: str
    p_decimals: int
    p_floor: float
    p_leading_zero: bool
    missing: str
    size: str
    placement: str
    caption_period: bool
    notes_lead: str
    notes_size: str
    notes_width: str
    notes_skip: str
    tabcolsep: str
    arraystretch: str


def table_style(param, **overrides):
    """The paper's table style, read through the driver's param(); keyword arguments override settings by field
    name (size="scriptsize" for table_size)."""
    if not callable(param):
        raise TypeError("table_style: pass the driver's param function: table_style(param)")
    fields = {name.removeprefix("table_"): name for name in TABLE_SETTINGS}
    unknown = sorted(set(overrides) - set(fields))
    if unknown:
        raise TypeError(f"table_style: no setting named {', '.join(unknown)}; the settings are "
                        f"{', '.join(fields)}")
    values = {}
    for field, name in fields.items():
        if field in overrides:
            values[field] = overrides[field]
            continue
        try:
            values[field] = param(name)
        except (KeyError, LookupError):
            raise KeyError(f"no parameter {name} in analysis/params.yml: the table writer needs every table_* "
                           "setting (research-kit's scaffold.py add-tables adds missing ones)") from None
    return _checked(values)


def _checked(v):
    def bad(field, why):
        raise ValueError(f"table_style: table_{field}: {why}")
    thresholds = [] if v["star_thresholds"] is None else list(_items(v["star_thresholds"]))
    markers = [] if v["star_markers"] is None else list(_items(v["star_markers"]))
    if len(thresholds) != len(markers):
        bad("star_markers", f"{len(markers)} markers for {len(thresholds)} thresholds")
    for t in thresholds:
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 < t < 1:
            bad("star_thresholds", f"{t!r} is not a number between 0 and 1")
        if _exact(t) is None:
            bad("star_thresholds", f"{t!r} doesn't print exactly with {MAX_DECIMALS} decimals or fewer")
    if len(set(thresholds)) != len(thresholds):
        bad("star_thresholds", "a threshold is given twice")
    for m in markers:
        if m not in MARKERS:
            bad("star_markers", f"{m!r} is not one of {', '.join(MARKERS)}")
    if len(set(markers)) != len(markers):
        bad("star_markers", "a marker is given twice")
    out = dict(v, star_thresholds=tuple(float(t) for t in thresholds), star_markers=tuple(markers))
    for field in ("decimals", "p_decimals"):
        out[field] = _decimals(v[field], f"table_{field}")
    floor = v["p_floor"]
    if isinstance(floor, bool) or not isinstance(floor, (int, float)) or not 0 < floor < 1 or _exact(floor) is None:
        bad("p_floor", f"{floor!r} is not a number between 0 and 1 that prints exactly")
    out["p_floor"] = float(floor)
    for field in ("p_leading_zero", "caption_period"):
        if not isinstance(v[field], bool):
            bad(field, f"{v[field]!r} is not true or false")
    for field in _WORDS:
        if not isinstance(v[field], str):
            bad(field, f"{v[field]!r} is not a string")
    for field in ("notes_width", "notes_skip"):
        if not v[field].strip():
            bad(field, "is empty; it is a LaTeX length, such as '\\linewidth' or '6pt'")
    for field in _PAIRS:
        pair = list(_items(v[field]))
        if len(pair) != 2 or not all(isinstance(s, str) for s in pair):
            bad(field, f"{v[field]!r} is not two strings, the opening and the closing one")
        out[field] = tuple(pair)
    return TableStyle(**out)


def _items(value):
    return value if isinstance(value, (list, tuple)) else [value]


def _decimals(d, what="decimals"):
    if isinstance(d, bool) or not isinstance(d, (int, float)) or d != int(d) or not 0 <= d <= MAX_DECIMALS:
        raise ValueError(f"{what}: {d!r} is not a whole number from 0 to {MAX_DECIMALS}")
    return int(d)


def _missing(x):
    """None, a NaN of any float type, or pandas' NA."""
    if x is None:
        return True
    pandas = sys.modules.get("pandas")
    if pandas is not None and x is getattr(pandas, "NA", None):
        return True
    try:
        return bool(x != x)
    except (TypeError, ValueError):
        return False


def _probability(p):
    v = _number(p, "p")
    if not 0 <= v <= 1:
        raise ValueError(f"p: {v!r} is not a p-value (between 0 and 1)")
    return v


def _number(x, what="x"):
    if isinstance(x, (str, bytes, bool)) or hasattr(x, "__len__"):
        raise TypeError(f"{what}: {x!r} is not one number (the table writer takes one value at a time)")
    v = float(x)
    if math.isinf(v):
        raise ValueError(f"{what}: an infinite value has no place in a table")
    return v


def _fixed(v, d):
    return "%.*f" % (d, v)


def _zero(text):
    return not any(c in "123456789" for c in text)


def _exact(t):
    """t with the fewest decimals from 2 to MAX_DECIMALS whose text reads back as t, or None."""
    for d in range(2, MAX_DECIMALS + 1):
        s = _fixed(t, d)
        if float(s) == t:
            return s
    return None


def _group(digits, sep):
    if not sep or len(digits) <= GROUP:
        return digits
    head = len(digits) % GROUP or GROUP
    return sep.join([digits[:head]] + [digits[i:i + GROUP] for i in range(head, len(digits), GROUP)])


def _signed(v, d, style, plus=False, prefix="", suffix=""):
    body = _fixed(abs(v), d)
    sign = "" if _zero(body) else MINUS if v < 0 else "+" if plus else ""
    whole, dot, frac = body.partition(".")
    return sign + prefix + _group(whole, style.thousands) + dot + frac + suffix


def _lead(text, style):
    return text[1:] if not style.p_leading_zero and text.startswith("0.") else text


def tex_number(x, style, decimals=None, plus=False, prefix="", suffix=""):
    """One number for a table cell: a real minus, no sign on a value that prints as zero, thousands separators
    from four integer digits; plus=True prints + on a positive value; prefix goes after the sign (\\$), suffix
    after the digits (\\%)."""
    if _missing(x):
        return style.missing
    d = style.decimals if decimals is None else _decimals(decimals)
    return _signed(_number(x), d, style, plus, prefix, suffix)


def star_marker(p, style):
    """The marker of the smallest threshold p is strictly below, as $^{**}$; "" for none."""
    if _missing(p):
        return ""
    v = _probability(p)
    if not style.star_thresholds:
        return ""
    below = [(t, m) for t, m in zip(style.star_thresholds, style.star_markers) if v < t]
    return "$^{" + min(below)[1] + "}$" if below else ""


def star_legend(style):
    """The markers' legend, from the largest threshold down: $^{*}p<0.10$, $^{**}p<0.05$."""
    pairs = sorted(zip(style.star_thresholds, style.star_markers), reverse=True)
    if not pairs:
        return ""
    return ", ".join("$^{" + m + "}p<" + _lead(_exact(t), style) + "$" for t, m in pairs) + "."


def p_cell(p, style):
    """A p-value: never printed as zero or on the other side of a star threshold (it gets more decimals instead);
    below the floor, $<$ and the floor."""
    if _missing(p):
        return style.missing
    v = _probability(p)
    if v < style.p_floor:
        return "$<$" + _lead(_exact(style.p_floor), style)
    d = style.p_decimals
    while d < MAX_DECIMALS and (_zero(_fixed(v, d)) or _crosses(v, d, style)):
        d += 1
    return _lead(_fixed(v, d), style)


def _crosses(v, d, style):
    shown = float(_fixed(v, d))
    return any((shown < t) != (v < t) for t in style.star_thresholds)


def se_cell(se, style, decimals=None):
    """A standard error inside the paper's brackets: (0.123)."""
    if _missing(se):
        return style.missing
    return style.se_brackets[0] + tex_number(se, style, decimals) + style.se_brackets[1]


def interval_cell(lo, hi, style, decimals=None):
    """An interval: [$-$0.12, 0.30]. A bound that prints as zero but isn't gets more decimals, so its sign shows."""
    if _missing(lo) or _missing(hi):
        return style.missing
    d = style.decimals if decimals is None else _decimals(decimals)
    bounds = []
    for x in (_number(lo, "lo"), _number(hi, "hi")):
        w = d
        while x != 0 and _zero(_fixed(x, w)) and w < MAX_DECIMALS:
            w += 1
        text = _signed(x, w, style)
        bounds.append(MINUS + text if x < 0 and _zero(text) else text)
    return style.interval_brackets[0] + style.interval_sep.join(bounds) + style.interval_brackets[1]


def table_row(cells):
    """Cells joined into one row: a & b & c \\\\."""
    cells = list(cells)
    if not all(isinstance(c, str) for c in cells):
        raise TypeError("table_row: every cell is a string (format numbers with tex_number first)")
    return " & ".join(cells) + " \\\\"


def header_band(groups, columns, lead=1):
    """A header row whose labels span groups of data columns, and its \\cmidrule line. groups: (label, first key,
    last key) for each group; columns: the data columns' keys in order, after `lead` label columns."""
    band, cmids, cursor = [""] * lead, [], lead + 1
    for label, first, last in groups:
        lo, hi = lead + columns.index(first) + 1, lead + columns.index(last) + 1
        band += [""] * (lo - cursor) + ["\\multicolumn{%d}{c}{%s}" % (hi - lo + 1, label)]
        cmids.append("\\cmidrule(lr){%d-%d}" % (lo, hi))
        cursor = hi + 1
    band += [""] * (lead + len(columns) - cursor + 1)
    return " & ".join(band) + " \\\\", " ".join(cmids)


def tex_table(colspec, rows, style, caption=None, label=None, notes=None, landscape=False):
    """A booktabs table: the rows (header rows, \\midrule lines and body, as written) between \\toprule and
    \\bottomrule, then the notes, with the star legend whenever a row carries a marker. With a caption, the whole
    float; without one, the body only, for a manuscript that holds the float and \\inputs the file."""
    rows = list(rows)
    if not all(isinstance(r, str) for r in rows):
        raise TypeError("tex_table: rows are strings")
    if caption is None and (label is not None or landscape):
        raise ValueError("tex_table: a label or landscape needs a caption; without one the manuscript holds "
                         "the float")
    if caption is not None and style.caption_period and not caption.rstrip().endswith("."):
        raise ValueError(f"tex_table: the paper's captions end with a period: {caption!r}")
    body = ["\\begingroup"]
    if style.size:
        body.append("\\" + style.size)
    if style.tabcolsep:
        body.append("\\setlength{\\tabcolsep}{" + style.tabcolsep + "}")
    if style.arraystretch:
        body.append("\\renewcommand{\\arraystretch}{" + style.arraystretch + "}")
    body += ["\\begin{tabular}{" + colspec + "}", "\\toprule", *rows, "\\bottomrule", "\\end{tabular}"]
    marked = any("$^{" + m + "}$" in r for r in rows for m in style.star_markers)
    text = " ".join(t for t in ((notes or "").strip(), star_legend(style) if marked else "") if t)
    if text:
        size = "\\" + style.notes_size if style.notes_size else ""
        body += ["\\par\\vspace{" + style.notes_skip + "}",
                 "\\begin{minipage}{" + style.notes_width + "}" + size,
                 " ".join(t for t in (style.notes_lead, text) if t),
                 "\\end{minipage}"]
    body.append("\\endgroup")
    if caption is None:
        return "\n".join(body) + "\n"
    place = "[" + style.placement + "]" if style.placement else ""
    out = ["\\begin{table}" + place, "\\centering", "\\caption{" + caption + "}"]
    if label is not None:
        out.append("\\label{" + label + "}")
    out += body + ["\\end{table}"]
    if landscape:
        out = ["\\begin{landscape}"] + out + ["\\end{landscape}"]
    return "\n".join(out) + "\n"


def write_tex(text, path, made_by=None):
    """Write a table file (UTF-8, \\n line endings), creating its folder; its first line names the script that
    wrote it (by default the running script's base name). The path comes from analysis/params.yml."""
    if not isinstance(text, str):
        raise TypeError("write_tex: text is one string, as tex_table() returns")
    who = _running_script() if made_by is None else made_by
    first = "% Generated by " + who + "; edit the code that writes it, not this file." if who else \
        "% Generated; edit the code that writes it, not this file."
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(first + "\n" + text)
    return path


def _running_script():
    arg = sys.argv[0] if sys.argv else ""
    return "" if arg in ("", "-c", "-") else Path(arg).name
