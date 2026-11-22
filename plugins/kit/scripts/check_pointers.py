#!/usr/bin/env python3
"""Every path cited in backticks in the state files and CLAUDE.md must exist (spec §5.1).

A backticked span is a path candidate only if it matches PATH_RE, contains no `*`, and
(after stripping a trailing :NN / :NN-MM) either ends with "/" (a directory pointer) or its
last path segment has an extension in FILE_EXTS (case-sensitive). Anything else (config
keys, module names, "read/write", "i.e") is not a pointer.

Exit: 0 all exist, 1 some missing, 2 error.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

TICK_RE = re.compile(r"`([^`\n]+)`")
PATH_RE = re.compile(r"^[A-Za-z0-9_./~-]+(?::\d+(?:-\d+)?)?$")
FILE_EXTS = {"md", "tex", "bib", "R", "r", "Rmd", "qmd", "py", "sh", "yml", "yaml", "json", "csv",
             "tsv", "txt", "pdf", "png", "jpg", "svg", "rds", "feather", "parquet", "log", "sty", "cls"}
FILES = ("state/CURRENT_STATE.md", "state/DECISIONS.md", "state/CLAIMS_LEDGER.md", "CLAUDE.md")


def candidates(text: str):
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in TICK_RE.finditer(line):
            span = m.group(1)
            if "*" in span or not PATH_RE.match(span):
                continue
            path = re.sub(r":\d+(?:-\d+)?$", "", span)
            last = path.rstrip("/").rsplit("/", 1)[-1] if not path.endswith("/") else ""
            if path.endswith("/") or ("." in last and last.rsplit(".", 1)[1] in FILE_EXTS):
                yield lineno, path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    if not (a.project / FILES[0]).is_file():
        print(f"check_pointers: ERROR: {a.project / FILES[0]}: file not found", file=sys.stderr)
        return 2
    missing = 0
    for rel in FILES:
        f = a.project / rel
        if not f.is_file():
            continue
        for lineno, path in candidates(f.read_text(encoding="utf-8")):
            p = Path(os.path.expanduser(path))
            if not (p if p.is_absolute() else a.project / p).exists():
                print(f"missing: {path} ({rel}:{lineno})")
                missing += 1
    print(f"{missing} missing pointer(s)" if missing else "all pointers exist")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
