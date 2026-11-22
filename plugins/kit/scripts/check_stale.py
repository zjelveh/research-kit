#!/usr/bin/env python3
"""Confirm replaced wording is gone everywhere (spec §5.6 step 5).

Whitespace-insensitive, so a phrase wrapped across .tex lines is still found.
Scans the paper's manuscript (the files lint.paper.globs match, what they \\input, the .bib files they name, and the
.tex and .bib files directly beside them, such as a title page), slides/ and notes/, excluding notes/memos/ and
notes/lit/searches/. Frozen copies in other folders of the clone are skipped.
Exit: 0 all clean, 1 something still present, 2 usage or config error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_bib import manuscript  # noqa: E402
from kitlib import KitError, load_config  # noqa: E402

EXTS = {".tex", ".md", ".bib"}
EXCLUDE = ("notes/memos/", "notes/lit/searches/")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def scan_files(project: Path, cfg: dict) -> list[Path]:
    files = []
    paper = project / cfg["paper_dir"]
    if paper.is_dir():
        real, globs = paper.resolve(), cfg["lint"]["paper"]["globs"]
        doc = manuscript(paper, globs)
        if not doc.files:
            raise KitError(f"no files match lint.paper.globs {globs} in {paper}")
        for name in doc.unresolved:
            print(f"check_stale: warning: \\input {name} not found; not scanned", file=sys.stderr)
        root_dirs = {p.resolve().parent for g in globs for p in paper.glob(g) if p.is_file()}
        beside = {p.resolve() for d in root_dirs for p in d.iterdir() if p.is_file() and p.suffix in (".tex", ".bib")}
        found = set()
        for p in {*doc.files, *doc.bibs, *beside}:  # resolved paths; TeX's own .bib files are dropped
            if p.is_relative_to(real):
                found.add(paper / p.relative_to(real))
            elif p.is_relative_to(project):
                found.add(p)
        files += sorted(found)
    for d in ("slides", "notes"):
        base = project / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(project).as_posix()
            if p.is_file() and p.suffix in EXTS and not rel.startswith(EXCLUDE) \
                    and "/.git/" not in f"/{rel}":
                files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("phrases", nargs="*")
    a = ap.parse_args(argv)
    if not a.phrases:
        print("usage: check_stale.py [--project DIR] \"old phrase\" [...]", file=sys.stderr)
        return 2
    project = a.project.resolve()
    try:
        cfg = load_config(project)
        files = {p: norm(p.read_text(encoding="utf-8", errors="replace")) for p in scan_files(project, cfg)}
    except KitError as e:
        print(f"check_stale: ERROR: {e}", file=sys.stderr)
        return 2
    bad = False
    for phrase in a.phrases:
        q, hits = norm(phrase), 0
        for p, text in files.items():
            n = text.count(q)
            if n:
                hits += n
                print(f"STILL PRESENT ({n}x) {p.relative_to(project).as_posix()} <- \"{phrase}\"")
        if hits:
            bad = True
        else:
            print(f"clean: \"{phrase}\"")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
