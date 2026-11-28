#!/usr/bin/env python3
"""Add research-kit's table writer to a project: `scaffold.py add-tables r|python` (table writer spec).

It copies the writer (templates/tables/tex_tables.R or .py) into the project's library, appends the table_*
settings analysis/params.yml lacks (from the table style in effect: the personal table-style.yml entry by entry
over the kit's), and commits those files alone. TABLE_SETTINGS names the settings; both writers carry the same
names, and the kit's defaults/table-style.yml holds all but the two star entries, which each project chooses.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_params  # noqa: E402
import scaffold  # noqa: E402
from code_scan import library_folders, r_file  # noqa: E402
from kitlib import DEFAULTS, PLUGIN_ROOT, KitError, find_project, git, load_config, personal_dir  # noqa: E402

TABLE_SETTINGS = (
    "table_star_thresholds", "table_star_markers", "table_decimals", "table_thousands", "table_se_brackets",
    "table_interval_brackets", "table_interval_sep", "table_p_decimals", "table_p_floor", "table_p_leading_zero",
    "table_missing", "table_size", "table_placement", "table_caption_period", "table_notes_lead",
    "table_notes_size", "table_notes_width", "table_notes_skip", "table_tabcolsep", "table_arraystretch",
)
STARS = ("table_star_thresholds", "table_star_markers")
STAR_COMMENTS = {"table_star_thresholds": "# p-value thresholds for the table stars, any order; [] for no stars",
                 "table_star_markers": "# The stars' markers, in the order of the thresholds (*, **, ***, \\dagger "
                                       "or \\ddagger); [] for no stars"}
STYLE_FILE = "table-style.yml"
TEMPLATES = PLUGIN_ROOT / "templates" / "tables"
WRITERS = {"r": "tex_tables.R", "python": "tex_tables.py"}
SECTION = ("# The paper's table style, read by the table writer (tex_tables) with table_style(param); a table "
           "overrides a setting in its driver.")
NAMESPACE = "pkg/r/NAMESPACE"
R_TOP = re.compile(r"^([A-Za-z.][A-Za-z0-9._]*)[ \t]*(?:<<-|<-|=(?!=))", re.M)


def style_entries(text: str, label: str) -> dict[str, tuple[str, list[str]]]:
    """{name: (value as written, its comment lines)} of a table-style file, checked with the params rules."""
    entries, problems = kit_params.read_text(text, label)
    if problems:
        raise KitError("; ".join(problems))
    unknown = sorted(set(entries) - set(TABLE_SETTINGS))
    if unknown:
        raise KitError(f"{label}: {', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not a table setting; "
                       f"the settings are {', '.join(TABLE_SETTINGS)}")
    out, comment = {}, []
    for line in text.removeprefix("﻿").splitlines():
        if not line.strip():
            comment = []
        elif line.startswith("#"):
            comment.append(line)
        else:
            name, raw = kit_params.ENTRY.fullmatch(line).groups()
            out[name], comment = (raw.strip(), comment), []
    return out


def style_in_effect() -> dict[str, tuple[str, list[str]]]:
    """The kit's table style with the personal file's entries over it, entry by entry."""
    default = DEFAULTS / STYLE_FILE
    merged = style_entries(default.read_text(encoding="utf-8"), str(default))
    personal = personal_dir() / STYLE_FILE
    if personal.is_file():
        merged |= style_entries(personal.read_text(encoding="utf-8"), str(personal))
    return merged


def parse_stars(spec: str) -> dict[str, tuple[str, list[str]]]:
    """--stars '*:0.1,**:0.05,***:0.01' as the two star entries."""
    pairs = []
    for part in spec.split(","):
        marker, colon, threshold = part.strip().rpartition(":")
        if not colon or not marker.strip():
            raise KitError(f"--stars: {part.strip()!r} is not marker:threshold; write --stars '*:0.1,**:0.05,***:0.01'")
        try:
            value = kit_params.parse_value(threshold)
        except ValueError:
            value = None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise KitError(f"--stars: {threshold.strip()!r} is not a number")
        pairs.append((marker.strip(), threshold.strip()))
    return {"table_star_thresholds": ("[" + ", ".join(t for _, t in pairs) + "]",
                                      [STAR_COMMENTS["table_star_thresholds"]]),
            "table_star_markers": ("[" + ", ".join("'" + m.replace("'", "''") + "'" for m, _ in pairs) + "]",
                                   [STAR_COMMENTS["table_star_markers"]])}


def writer_module():
    """The Python writer, for its checks of a style (the same checks both writers make)."""
    spec = importlib.util.spec_from_file_location("kit_tex_tables", TEMPLATES / WRITERS["python"])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def check_style(values: dict[str, object]) -> None:
    try:
        writer_module().table_style(lambda name: values[name])
    except (KeyError, TypeError, ValueError) as e:
        raise KitError(str(e).strip('"')) from None


def candidates(project: Path, cfg: dict, lang: str) -> list[str]:
    """The library folders that could hold this language's writer (spec: Where)."""
    packages, out = cfg["packages"], []
    for f in library_folders(project, cfg):
        folder = project / f
        if not folder.is_dir():
            continue
        if f == f"pkg/{lang}" or f.startswith(f"pkg/{lang}/"):
            if lang not in packages:
                continue
            target = "pkg/r/R" if lang == "r" else f"pkg/python/src/{packages['python']}"
        elif f.startswith("pkg/"):
            continue
        else:
            names = [p.name for p in folder.iterdir() if p.is_file()]
            has_r = any(r_file(n) and n != ".Rprofile" for n in names)
            has_py = any(n.endswith(".py") for n in names)
            if not ((has_r if lang == "r" else has_py) or not (has_r or has_py)):
                continue
            target = f
        if target not in out:
            out.append(target)
    return out


def choose_folder(project: Path, cfg: dict, lang: str, into: str | None) -> str:
    found = candidates(project, cfg, lang)
    what = scaffold.LANG_NAMES[lang]
    if into is not None:
        rel = Path(os.path.normpath(into)).as_posix().rstrip("/")
        if rel not in found:
            raise KitError(f"{into} is not a library folder for {what} code (the candidates: "
                           f"{', '.join(found) if found else 'none'})")
        return rel
    if len(found) == 1:
        return found[0]
    if not found:
        raise KitError(f"the project has no library folder for {what} code: add a folder to library: in "
                       f".claude/research.yml, or a package (scaffold.py add-package {lang}), then rerun add-tables")
    raise KitError(f"several library folders could hold the writer ({', '.join(found)}); choose one with --into")


def r_names(text: str) -> set[str]:
    """The names an R file assigns at the top level (column 0), private ones included."""
    return set(R_TOP.findall(text))


def r_clashes(project: Path, cfg: dict, target: str) -> tuple[list[str], list[str]]:
    """(the project's files' clashing names, other copies of the kit's writer) in the R library folders."""
    mine = r_names((TEMPLATES / WRITERS["r"]).read_text(encoding="utf-8"))
    hits, copies = [], []
    for folder in candidates(project, cfg, "r"):
        for p in sorted((project / folder).iterdir()):
            rel = f"{folder}/{p.name}"
            if not p.is_file() or not r_file(p.name) or rel == target:
                continue
            if p.name == WRITERS["r"] and scaffold.kits_file(p):
                copies.append(rel)
                continue
            hits += [f"{rel}: {n}" for n in sorted(r_names(p.read_text(encoding="utf-8", errors="replace")) & mine)]
    return hits, copies


def namespace_text(text: str) -> str | None:
    """NAMESPACE with an export() line for each of the writer's public functions it lacks; None when nothing is
    missing or it exports by pattern. A file roxygen wrote (its header, one directive per line) is laid out as
    roxygen writes it, so a later roxygen run leaves no diff; any other file gets the lines at its end."""
    if re.search(r"(?m)^\s*exportPattern\(", text):
        return None
    public = sorted(n for n in r_names((TEMPLATES / WRITERS["r"]).read_text(encoding="utf-8"))
                    if not n.startswith("."))
    have = {name.strip().strip("\"'`") for inside in re.findall(r"\bexport\(([^)]*)\)", text, re.S)
            for name in inside.split(",")}
    new = [f"export({n})" for n in public if n not in have]
    if not new:
        return None
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    header = [line for line in lines if line.startswith("#")]
    directives = [line for line in lines if line.strip() and not line.startswith("#")]
    roxygen = bool(lines) and lines[0].startswith("# Generated by roxygen2") and \
        all(re.fullmatch(r"[A-Za-z0-9_.]+\([^()]*\)", d.strip()) for d in directives)
    if roxygen:
        return nl.join(header + [""] + sorted(set(directives + new))) + nl
    return text + ("" if not text or text.endswith(("\n", "\r")) else nl) + nl.join(new) + nl


def write_exact(path: Path, text: str) -> None:
    """Write the text as given: no newline translation on any platform."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def uncommitted(project: Path, rel: str) -> bool:
    return bool(git(project, "status", "--porcelain", "--", rel).strip())


def cmd_add_tables(lang: str, project: Path, into: str | None = None, stars: str | None = None,
                   no_stars: bool = False) -> list[str]:
    """Add the writer and the settings the project lacks, in one commit; the paths committed ([] if none)."""
    project = find_project(Path(os.path.abspath(project)))
    scaffold.require_toplevel(project)
    cfg = load_config(project)
    if lang not in cfg["languages"]:
        raise KitError(f"languages in .claude/research.yml has no {lang}")
    if stars is not None and no_stars:
        raise KitError("give --stars or --no-stars, not both")
    folder = choose_folder(project, cfg, lang, into)
    target = f"{folder}/{WRITERS[lang]}"
    template = TEMPLATES / WRITERS[lang]
    path = project / target
    if path.exists() or path.is_symlink():
        if not path.is_file() or not scaffold.kits_file(path):
            raise KitError(f"{target} already exists and is not the kit's writer; rename or move it, then rerun "
                           "add-tables")
        status = "current" if path.read_bytes() == template.read_bytes() else "kept"
    else:
        status = "new"

    params = project / kit_params.PIPELINE
    if not params.is_file():
        raise KitError(f"{kit_params.PIPELINE} is missing; run scaffold.py add-params first")
    if kit_params.foreign(project):
        raise KitError("; ".join(kit_params.foreign(project)))
    pipe, expl, problems = kit_params.load(project)
    if problems:
        raise KitError("fix the parameter files first: " + "; ".join(problems))
    in_explore = sorted(n for n in expl if n.startswith("table_"))
    if in_explore:
        raise KitError(f"{', '.join(in_explore)} {'is' if len(in_explore) == 1 else 'are'} in "
                       f"{kit_params.EXPLORE}; the table settings belong in {kit_params.PIPELINE} (move "
                       f"{'it' if len(in_explore) == 1 else 'them'} there, with approval)")
    have = [n for n in STARS if n in pipe]
    if len(have) == 1:
        missing = next(n for n in STARS if n not in pipe)
        raise KitError(f"{kit_params.PIPELINE} has {have[0]} but not {missing}; add it, with approval, then rerun")
    if have and (stars is not None or no_stars):
        raise KitError(f"{kit_params.PIPELINE} already sets the star rule; changing a parameter needs approval, so "
                       "edit it there instead of passing --stars or --no-stars")
    effect = style_in_effect()
    if stars is not None:
        effect |= parse_stars(stars)
    elif no_stars:
        effect |= {n: ("[]", [STAR_COMMENTS[n]]) for n in STARS}
    if not have and sum(n in effect for n in STARS) == 1:
        raise KitError(f"{personal_dir() / STYLE_FILE} sets only one of {' and '.join(STARS)}; set both, or neither")
    if not have and not all(n in effect for n in STARS):
        raise KitError("choose a star rule: --stars '<marker>:<threshold>,...' (as '*:0.1,**:0.05,***:0.01') or "
                       "--no-stars")
    missing = [n for n in TABLE_SETTINGS if n not in pipe]
    check_style({n: pipe[n][0] if n in pipe else kit_params.parse_value(effect[n][0]) for n in TABLE_SETTINGS})

    if lang == "r":
        clashes, copies = r_clashes(project, cfg, target)
        if copies:
            raise KitError(f"the kit's writer is already in {', '.join(copies)}; one copy per R library (they would "
                           "replace each other's functions): use that one, or delete it and rerun add-tables")
        if clashes:
            raise KitError("the R library already defines names the writer uses (a folder library loads every file "
                           f"into one environment, so one would replace the other): {'; '.join(clashes)}; rename "
                           "the project's, then rerun add-tables")
    namespace = None
    if folder == "pkg/r/R" and (project / NAMESPACE).is_file():
        namespace = namespace_text((project / NAMESPACE).read_bytes().decode("utf-8"))

    own = ([target] if status == "new" else []) + ([str(kit_params.PIPELINE)] if missing else []) + \
        ([NAMESPACE] if namespace is not None else [])
    for rel in own:
        if rel != target and uncommitted(project, rel):
            raise KitError(f"{rel} has uncommitted changes; commit or discard them, then rerun add-tables")
    if status == "kept":
        print(f"add-tables: kept {target}: it differs from this kit's copy (an older kit, or the project's edits); "
              "to take this kit's copy, delete it and rerun")
    elif status == "current":
        print(f"add-tables: {target} is current")
    if not own:
        print("add-tables: the writer and its settings are all there")
        notes(project, lang, folder, target)
        return []
    scaffold.refuse_ignored(project, own)
    scaffold.require_slides_gate_passing(project, cfg)

    orig = git(project, "rev-parse", "HEAD").strip()
    try:
        if status == "new":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(template.read_bytes())
        if missing:
            text = params.read_bytes().decode("utf-8")
            nl = "\r\n" if "\r\n" in text else "\n"            # keep the file's own line endings
            blocks = [nl.join((effect[n][1] or [f"# {n}"]) + [f"{n}: {effect[n][0]}"]) for n in missing]
            end = "" if not text or text.endswith(("\n", "\r")) else nl
            write_exact(params, text + end + nl + SECTION + nl + nl + (nl + nl).join(blocks) + nl)
        if namespace is not None:
            write_exact(project / NAMESPACE, namespace)
        git(project, "add", "--", *own)
        git(project, "commit", "-q", "-m", f"Add the table writer {target} and its settings (research-kit)", "--",
            *own)
    except BaseException as e:
        err = str(e) or type(e).__name__
        head = git(project, "rev-parse", "HEAD").strip()
        if head != orig:
            raise KitError(f"{err} — the commit {head[:7]} already landed, so nothing was rolled back") from None
        scaffold.rollback(project, own, [target] if status == "new" else [])
        if isinstance(e, (KitError, OSError)):
            raise KitError(f"{err}\nadd-tables: rolled back; nothing was changed. If the commit check found a near "
                           "copy of a function the project already has, use the project's function or merge the "
                           "two (ask the user which), then rerun") from None
        raise
    sha = git(project, "rev-parse", "HEAD").strip()
    print(f"add-tables: committed {sha[:7]} in {project} (not pushed): {', '.join(own)}")
    if missing:
        print(f"add-tables: added {len(missing)} table setting{'s' if len(missing) != 1 else ''} to "
              f"{kit_params.PIPELINE}: {', '.join(missing)}")
    notes(project, lang, folder, target)
    return own


def notes(project: Path, lang: str, folder: str, target: str) -> None:
    if folder == "pkg/r/R":
        print('add-tables: R loads the installed package: run renv::install("./pkg/r") and renv::snapshot()')
    elif lang == "r" and not (project / folder / "load.R").is_file():
        print(f"add-tables: {folder} has no load.R: run scaffold.py add-loader {folder}, or source(\"{target}\") "
              "in the scripts that write tables")
    elif lang == "python" and not folder.startswith("pkg/"):
        print(f"add-tables: import {target} the way the project imports its library")
    call = "style <- table_style(param)" if lang == "r" else "style = table_style(param)"
    print(f"add-tables: in a driver, {call}, then tex_number(), star_marker(), se_cell(), tex_table() and "
          "write_tex() with that style")
