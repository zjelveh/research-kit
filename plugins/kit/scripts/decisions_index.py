#!/usr/bin/env python3
"""Regenerate the one-line-per-decision index in state/DECISIONS.md (spec §5.1).

Exit: 0 ok (or index current with --check), 1 index stale (--check), 2 error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, atomic_write  # noqa: E402

HEAD_RE = re.compile(r"^### (D-\d{3,}) — (.+) \((\d{4}-\d{2}-\d{2})\)\s*$")
BEGIN, END = "<!-- BEGIN INDEX -->", "<!-- END INDEX -->"


def build(text: str, path: Path) -> str:
    lines = text.split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1 or lines.index(END) < lines.index(BEGIN):
        raise KitError(f"{path}: needs exactly one '{BEGIN}' followed by one '{END}'")
    entries, seen = [], set()
    for lineno, line in enumerate(lines, start=1):
        if not line.startswith("### D-"):
            continue
        m = HEAD_RE.match(line)
        if not m:
            raise KitError(f"{path}:{lineno}: heading must be '### D-NNN — Title (YYYY-MM-DD)'")
        if m.group(1) in seen:
            raise KitError(f"{path}:{lineno}: duplicate decision id {m.group(1)}")
        seen.add(m.group(1))
        entries.append(f"- {m.group(1)} ({m.group(3)}): {m.group(2)}")
    b, e = lines.index(BEGIN), lines.index(END)
    return "\n".join(lines[:b + 1] + entries + lines[e:])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--check", action="store_true", help="exit 1 if the index is stale; write nothing")
    a = ap.parse_args(argv)
    path = a.project / "state" / "DECISIONS.md"
    try:
        if not path.is_file():
            raise KitError(f"{path}: file not found")
        old = path.read_text(encoding="utf-8")
        new = build(old, path)
    except KitError as e:
        print(f"decisions_index: ERROR: {e}", file=sys.stderr)
        return 2
    if a.check:
        print("index current" if new == old else "index STALE: run decisions_index.py")
        return 0 if new == old else 1
    atomic_write(path, new)
    print("index written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
