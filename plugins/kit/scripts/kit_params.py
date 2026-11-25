"""The project's parameter files (code spec section 2): analysis/params.yml for the pipeline and
analysis/explore/params.yml for quick questions. Reading them, and checking their format.

The format is a strict subset of YAML that the project's readers (analysis/params.R, analysis/params.py)
parse without packages: one `name: value` per line, each entry preceded by a comment line saying what
the value is and why. Values are numbers, single-quoted strings (dates and paths among them), true or
false, or a one-line list of numbers or single-quoted strings.
"""
from __future__ import annotations

import re
from pathlib import Path

PIPELINE = Path("analysis") / "params.yml"
EXPLORE = Path("analysis") / "explore" / "params.yml"
NAME = re.compile(r"[a-z][a-z0-9_]*")
ENTRY = re.compile(r"([a-z][a-z0-9_]*):[ ]?(.*)")
NUMBER = re.compile(r"-?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
QUOTED = re.compile(r"'((?:[^']|'')*)'")
ITEM = re.compile(r"\s*('(?:[^']|'')*'|[^,]+?)\s*(,|$)")


def parse_value(text: str):
    """A value as the readers return it, or raise ValueError with what is wrong."""
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    if NUMBER.fullmatch(text):
        return float(text) if any(c in text for c in ".eE") else int(text)
    if m := QUOTED.fullmatch(text):
        return m.group(1).replace("''", "'")
    if text.startswith("[") and text.endswith("]"):
        inner, items, pos = text[1:-1].strip(), [], 0
        while inner and pos < len(inner):
            m = ITEM.match(inner, pos)
            if not m or m.end() == pos:
                raise ValueError(f"cannot read the list {text}")
            item = parse_value(m.group(1))
            if isinstance(item, (list, bool)):
                raise ValueError(f"a list holds numbers or single-quoted strings only: {text}")
            items.append(item)
            pos = m.end()
        if len({isinstance(i, str) for i in items}) > 1:
            raise ValueError(f"a list holds numbers only or strings only, not both: {text}")
        return items
    raise ValueError(f"{text!r} is not a number, a single-quoted string, true/false or a one-line list; "
                     "quote strings, dates and paths in single quotes")


def read_file(path: Path) -> tuple[dict[str, tuple[object, int, str]], list[str]]:
    """{name: (value, line, about)} and the format problems, as `file:line: message`."""
    return read_text(path.read_text(encoding="utf-8", errors="replace"), str(path)) if path.is_file() else ({}, [])


def read_text(text: str, label: str) -> tuple[dict[str, tuple[object, int, str]], list[str]]:
    entries, problems, comment = {}, [], []
    for n, line in enumerate(text.removeprefix("\ufeff").splitlines(), 1):
        where = f"{label}:{n}"
        if not line.strip():
            comment = []
            continue
        if line.startswith("#"):
            comment.append(line.lstrip("#").strip())
            continue
        m = ENTRY.fullmatch(line)
        if not m:
            problems.append(f"{where}: expected `name: value` (a lowercase name at the start of the line) "
                            "or a comment line")
            comment = []
            continue
        name, raw = m.groups()
        try:
            value = parse_value(raw)
        except ValueError as e:
            problems.append(f"{where}: {name}: {e}")
            value = None
        if not any(comment):
            problems.append(f"{where}: {name}: needs a comment line directly above saying what it is and why")
        if name in entries:
            problems.append(f"{where}: {name} is already defined at line {entries[name][1]}")
        entries[name] = (value, n, " ".join(c for c in comment if c))
        comment = []
    return entries, problems


def _text(project: Path, rel: Path, texts: dict[Path, str | None] | None) -> str | None:
    if texts is not None and rel in texts:
        return texts[rel]
    path = project / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def kits(text: str) -> bool:
    """A parameter file the kit wrote says research-kit in its first lines; another is the project's own."""
    return "research-kit" in "".join(text.removeprefix("\ufeff").splitlines(True)[:5])


def foreign(project: Path, texts: dict[Path, str | None] | None = None) -> list[str]:
    """Notes for parameter files the kit didn't write, which load() leaves out."""
    return [f"{rel} is not the kit's parameter file (no research-kit header), so it is ignored; if it is the "
            "kit's, restore its header, and if it is the project's own, rename it and run scaffold.py add-params"
            for rel in (PIPELINE, EXPLORE) if (t := _text(project, rel, texts)) is not None and not kits(t)]


def load(project: Path, texts: dict[Path, str | None] | None = None) -> tuple[dict, dict, list[str]]:
    """(pipeline entries, explore entries, problems). A name may be defined in only one of the files.
    `texts` gives a file's content (None: absent) instead of reading it, as the commit gate does. A file
    the kit didn't write is left out (see foreign())."""
    def one(rel):
        text = _text(project, rel, texts)
        return read_text(text, str(rel)) if text is not None and kits(text) else ({}, [])
    (pipe, p1), (expl, p2) = one(PIPELINE), one(EXPLORE)
    clash = [f"{EXPLORE}:{expl[n][1]}: {n} is already a pipeline parameter ({PIPELINE})"
             for n in sorted(set(pipe) & set(expl))]
    return pipe, expl, p1 + p2 + clash
