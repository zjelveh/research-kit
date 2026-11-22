#!/usr/bin/env python3
"""Build numbers.tex and the ledger's generated table from the project's make_numbers scripts.

Runs analysis/numbers/make_numbers.R (Rscript) and/or make_numbers.py (uv run --locked), one per
language in research.yml, reads what each passed to emit_numbers(), checks the entries across both,
and writes both files together (research-kit languages spec §5.2). Exit: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import LANGUAGES, KitError, git, load_config  # noqa: E402

SCRIPTS = {"r": "analysis/numbers/make_numbers.R", "python": "analysis/numbers/make_numbers.py"}
TOOLS = {"r": "Rscript", "python": "uv"}
ENV_FILES = {"r": (".Rprofile", "renv.lock"), "python": ("pyproject.toml", "uv.lock")}
NAME_RE = re.compile(r"[a-z][A-Za-z]*")
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
BEGIN, END = "<!-- BEGIN GENERATED -->", "<!-- END GENERATED -->"
LEDGER = Path("state") / "CLAIMS_LEDGER.md"


def command(lang: str, script: str) -> list[str]:
    if lang == "r":
        return ["Rscript", script]
    return ["uv", "run", "--locked", "python", script]


def check_scripts(project: Path, languages: list[str]) -> None:
    for lang in LANGUAGES:
        exists = (project / SCRIPTS[lang]).is_file()
        if lang in languages and not exists:
            raise KitError(f"{SCRIPTS[lang]} is missing, but '{lang}' is in research.yml languages")
        if exists and lang not in languages:
            raise KitError(f"{SCRIPTS[lang]} exists, but '{lang}' is not in research.yml languages")
    for lang in languages:
        for f in ENV_FILES[lang]:
            if not (project / f).is_file():
                raise KitError(f"{f} is missing, so the {'R' if lang == 'r' else 'Python'} environment isn't set up")
    for lang in languages:
        if shutil.which(TOOLS[lang]) is None:
            raise KitError(f"{TOOLS[lang]} is not on the PATH; it is needed to run {SCRIPTS[lang]}")


def read_ledger(project: Path) -> tuple[Path, list[str], int, int]:
    path = project / LEDGER
    if not path.is_file():
        raise KitError(f"{path}: file not found")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        raise KitError(f"{path}: cannot read: {err}") from None
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    b = [i for i, line in enumerate(lines) if line == BEGIN]
    e = [i for i, line in enumerate(lines) if line == END]
    if len(b) != 1 or len(e) != 1 or e[0] <= b[0]:
        raise KitError(f"{path}: needs exactly one {BEGIN} marker followed by one {END} marker")
    return path, lines, b[0], e[0]


def run_script(project: Path, lang: str) -> list[dict]:
    script = SCRIPTS[lang]
    with tempfile.TemporaryDirectory(prefix=f"kit-numbers-{lang}-") as d:
        out = Path(d) / "entries.csv"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "R_PROFILE_USER")}
        env["KIT_NUMBERS_OUT"] = str(out)
        emit = "numbers_emit.R" if lang == "r" else "numbers_emit.py"
        env["KIT_NUMBERS_EMIT"] = str(Path(__file__).resolve().parent / emit)
        proc = subprocess.run(command(lang, script), cwd=project, env=env, capture_output=True,
                              stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
        sep = "" if not proc.stdout or proc.stdout.endswith("\n") else "\n"
        shown = (proc.stdout + sep + proc.stderr).strip()
        if proc.returncode != 0:
            tail = "\n".join(shown.splitlines()[-50:])
            raise KitError(f"{script} failed (exit {proc.returncode}):\n{tail}")
        if shown:
            print(f"--- output of {script} ---\n{shown}\n--- end of {script} ---", file=sys.stderr)
        if not out.is_file():
            raise KitError(f"{script} exited 0 but never called emit_numbers")
        try:
            with out.open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames != ["name", "value", "src"]:
                    raise KitError(f"{script}: emit_numbers output is malformed "
                                   f"(expected the header name,value,src, got {reader.fieldnames!r})")
                rows = list(reader)
        except (UnicodeDecodeError, csv.Error, OSError) as err:
            raise KitError(f"{script}: cannot read emit_numbers output: {err}") from None
    for row in rows:
        if set(row) != {"name", "value", "src"} or None in row.values():
            raise KitError(f"{script}: emit_numbers output row {row!r} is malformed "
                           "(expected name, value, src)")
        row["script"] = script
    return rows


def escape_pct(value: str) -> str:
    return re.sub(r"(?<!\\)%", r"\\%", value)


def balanced(value: str) -> bool:
    depth = 0
    for ch in re.sub(r"\\[{}]", "", value):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            return False
    return depth == 0


def source_commit(project: Path, name: str, src: str, script: str) -> tuple[str, str]:
    where = f"source '{src}' for \\{name} ({script})"
    if Path(src).is_absolute():
        raise KitError(f"{where} must be a path relative to the project root")
    if not (project / src).resolve().is_relative_to(project.resolve()):
        raise KitError(f"{where} resolves outside the project (via '..' or a symlink)")
    if not (project / src).exists():
        raise KitError(f"{where} does not exist")
    if not (project / src).is_file():
        raise KitError(f"{where} is not a file")
    spec = f":(literal){src}"
    try:
        git(project, "ls-files", "--error-unmatch", "--", spec)
    except KitError:
        raise KitError(f"{where} is untracked (exploratory); commit it first") from None
    if git(project, "status", "--porcelain", "--", spec).strip():
        raise KitError(f"{where} has uncommitted changes (exploratory); commit it first")
    sha, date = git(project, "log", "-1", "--format=%H %cs", "--", spec).strip().partition(" ")[::2]
    if not SHA_RE.fullmatch(sha) or not date:
        raise KitError(f"could not find the commit for '{src}'")
    return sha, date


def check_rows(project: Path, rows: list[dict]) -> list[dict]:
    seen: dict[str, str] = {}
    checked = []
    for r in rows:
        name, src, script = r["name"], r["src"], r["script"]
        if not NAME_RE.fullmatch(name):
            raise KitError(f"macro name '{name}' ({script}) must be letters only, camelCase, starting lowercase")
        if name in seen:
            where = script if seen[name] == script else f"{seen[name]} and {script}"
            raise KitError(f"duplicate macro name '{name}' in {where}")
        seen[name] = script
        value = escape_pct(r["value"])
        if not balanced(value):
            raise KitError(f"formatted value for \\{name} ({script}) has unbalanced braces: {value}")
        sha, date = source_commit(project, name, src, script)
        checked.append({**r, "value": value, "sha": sha, "date": date})
    return checked


def write_outputs(out_path: Path, ledger_path: Path, ledger: list[str], b: int, e: int,
                  rows: list[dict], scripts: list[str]) -> None:
    tex = [f"% Generated by research-kit numbers_build.py from {', '.join(scripts)}. Do not edit."]
    tex += [f"\\newcommand{{\\{r['name']}}}{{{r['value']}}}% src={r['src']} commit={r['sha']}" for r in rows]
    table = ["| Macro | Value | Source | Commit | Script | Date |", "|---|---|---|---|---|---|"]
    table += [f"| `\\{r['name']}` | {r['value']} | `{r['src']}` | {r['sha'][:10]} | `{r['script']}` | {r['date']} |"
              for r in rows]
    pairs = [(out_path, tex), (ledger_path, ledger[:b + 1] + table + ledger[e:])]
    tmps = [path.with_name(path.name + ".tmp") for path, _ in pairs]
    try:
        old = out_path.read_bytes() if out_path.exists() else None
        for tmp, (_, lines) in zip(tmps, pairs):
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as err:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)
        raise KitError(f"staging failed: {err}") from None
    for n, (tmp, (path, _)) in enumerate(zip(tmps, pairs)):
        try:
            tmp.replace(path)
        except OSError as err:
            restored = ""
            if n == 1:
                try:
                    if old is None:
                        out_path.unlink(missing_ok=True)
                    else:
                        out_path.write_bytes(old)
                    restored = "; numbers.tex was restored"
                except OSError as err2:
                    restored = f"; numbers.tex could NOT be restored ({err2})"
            for t in tmps:
                t.unlink(missing_ok=True)
            raise KitError(f"could not rename {tmp} to {path}: {err}{restored}") from None


def build(project: Path) -> tuple[int, Path]:
    cfg = load_config(project)
    try:
        inside = git(project, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except KitError:
        inside = False
    if not inside:
        raise KitError(f"{project} is not a git repository; numbers need committed sources")
    out_path = project / cfg["numbers_tex"]
    if not out_path.parent.is_dir():
        raise KitError(f"output directory {out_path.parent} does not exist (is the paper attached?)")
    read_ledger(project)  # fail fast on missing markers, before any script runs
    check_scripts(project, cfg["languages"])
    rows: list[dict] = []
    for lang in cfg["languages"]:
        rows += run_script(project, lang)
    checked = check_rows(project, rows)
    ledger_path, ledger, b, e = read_ledger(project)  # again: the scripts may have edited it
    write_outputs(out_path, ledger_path, ledger, b, e, checked, [SCRIPTS[x] for x in cfg["languages"]])
    return len(checked), out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        n, out = build(a.project.resolve())
    except KitError as e:
        print(f"numbers_build: ERROR: {e}", file=sys.stderr)
        return 2
    print(f"numbers_build: {n} macros written to {out} and {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
