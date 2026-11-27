#!/usr/bin/env python3
"""Frozen results: files the pipeline reads but doesn't remake, kept on purpose (frozen results spec).

  frozen.py add <file> --made-by <script> --why "<reason>" [--project P]
      add or replace the entry for <file> in analysis/frozen.yml, with its SHA-256; commits nothing

Paths are relative to the project root. A frozen file counts as made, for the code map and for the gate's
archive check, and its made_by script may be archived or deleted. The code map lists entries to check: a
missing file, a changed SHA-256, or a file git doesn't track (a fresh clone wouldn't have it).
Exit: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, find_project, git  # noqa: E402

FROZEN = "analysis/frozen.yml"
KEYS = ("path", "made_by", "why", "sha256")
HEADER = ("# Results the pipeline reads but doesn't remake, kept on purpose (research-kit). Write entries with:\n"
          "#   kit frozen.py add <file> --made-by <script> --why \"<reason>\"\n")


def parse(text: str | None, where: str = FROZEN) -> list[dict]:
    """The entries of a frozen.yml text (None or empty: none). Raises KitError when malformed."""
    if not text or not text.strip():
        return []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise KitError(f"{where}: not valid YAML: {e}") from None
    if data is None:
        return []
    if not isinstance(data, list):
        raise KitError(f"{where}: must be a list of entries with {', '.join(KEYS)}")
    for i, e in enumerate(data, 1):
        if not isinstance(e, dict) or set(e) != set(KEYS) or not all(isinstance(e[k], str) and e[k].strip()
                                                                     for k in KEYS):
            raise KitError(f"{where}: entry {i} must have exactly {', '.join(KEYS)}, each a non-empty string")
        for k in ("path", "made_by"):
            v = e[k]
            if v.startswith(("/", "./")) or "//" in v or ".." in v.split("/") or v.endswith("/"):
                raise KitError(f"{where}: entry {i}: {k} {v!r} must be a path from the project root, as "
                               "frozen.py add writes it")
    return data


def load(project: Path) -> list[dict]:
    path = project / FROZEN
    return parse(path.read_text(encoding="utf-8") if path.is_file() else None)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _inside(project: Path, rel: str) -> str:
    root = project.resolve()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise KitError(f"{rel} is outside the project")
    return path.relative_to(root).as_posix()


def add(project: Path, file: str, made_by: str, why: str) -> dict:
    rel, script = _inside(project, file), _inside(project, made_by)
    if not (project / rel).is_file():
        raise KitError(f"{rel} does not exist; a frozen result is a file the pipeline reads")
    in_index = git(project, "ls-files", "-z", "--", f":(literal){script}").strip("\0")
    in_head = git(project, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", f":(literal){script}",
                  check=False).strip("\0")
    if not in_index and not in_head:
        raise KitError(f"{script} is not a file git has (staged or in the last commit); --made-by names the "
                       f"script that made {rel}")
    if not why.strip() or (why.strip().startswith("<") and why.strip().endswith(">")):
        raise KitError("--why is empty or the placeholder; say why the file isn't remade")
    if not script.endswith((".R", ".r", ".py", ".sh")):
        raise KitError(f"--made-by {script} is not an R, Python or shell script")
    entry = {"path": rel, "made_by": script, "why": " ".join(why.split()), "sha256": sha256(project / rel)}
    entries = sorted([e for e in load(project) if e["path"] != rel] + [entry], key=lambda e: e["path"])
    body = yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=10_000)
    (project / FROZEN).write_text(HEADER + body, encoding="utf-8")
    return entry


def tracked(project: Path, rel: str) -> bool:
    return bool(git(project, "ls-files", "-z", "--", f":(literal){rel}").strip("\0"))


def problems(project: Path, entries: list[dict]) -> list[str]:
    """Entries to check, from the working tree: the file is missing, has changed, or git doesn't track it."""
    out = []
    for e in entries:
        path = project / e["path"]
        if not path.is_file():
            out.append(f"{e['path']}: frozen, but the file is missing")
            continue
        if sha256(path) != e["sha256"]:
            out.append(f"{e['path']}: frozen, but the file has changed since it was frozen (SHA-256 differs); "
                       "if the change is intended, run frozen.py add again")
        if not tracked(project, e["path"]):
            out.append(f"{e['path']}: frozen, but git doesn't track it, so a fresh clone won't have it: "
                       f"git add -f -- {e['path']}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add")
    a_.add_argument("file")
    a_.add_argument("--made-by", required=True)
    a_.add_argument("--why", required=True)
    a_.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        project = find_project(a.project)
        e = add(project, a.file, a.made_by, a.why)
        note = "" if tracked(project, e["path"]) else (
            f" git doesn't track {e['path']}, so a fresh clone won't have it: git add -f -- {e['path']}")
    except KitError as e:
        print(f"frozen: ERROR: {e}", file=sys.stderr)
        return 2
    print(f"frozen: {e['path']} recorded in {FROZEN} (made by {e['made_by']}; sha256 {e['sha256'][:12]}). "
          f"Commit it with the change it belongs to.{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
