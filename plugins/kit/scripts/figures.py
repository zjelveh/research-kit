#!/usr/bin/env python3
"""Figure design with Munzner's idioms (figures spec section 4).

  figures.py candidates --project P --task T [--shape S] [--key-types T,..] [--value-types T,..] [--intervals]
                        [--medium static|interactive|any]
  figures.py check --project P [--draft] [<figure> ...]

candidates lists the idioms in effect that serve the task, best fit first, each flagged when it doesn't
list the task, its shape differs or the types don't fit. With --intervals, idioms that draw intervals come
first and the others are flagged. check runs every check on the figure specs in
notes/figures/ (or on the named figures, all panels included), prints one line per finding,
<figure>: <severity> <check>: <message> [<attribute>], and ends with a line of counts.
Exit: 0 no errors, 1 an error in a spec, 2 usage, project or catalogue error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_checks import Context, Finding, run_checks  # noqa: E402
from figure_spec import SPEC_DIR, label, read_spec, spec_paths, substitution_steps  # noqa: E402
from idioms import first_sentence, load_catalogue, load_vocabulary  # noqa: E402
from kitlib import KitError, find_project  # noqa: E402


def _types(text: str | None, vocab: dict) -> list[str] | None:
    if text is None:
        return None
    types = [t.strip() for t in text.split(",") if t.strip()]
    bad = [t for t in types if t not in vocab["attribute_types"]]
    if bad:
        raise KitError(f"unknown type {', '.join(bad)}; use {', '.join(vocab['attribute_types'])}")
    return types


NO_FIT = 99


def type_fit(idiom: dict, key_types: list | None, value_types: list | None, vocab: dict) -> int:
    """How far the given types are from the idiom's: 0 when they match exactly, the summed substitution
    steps when they fit through substitutes, NO_FIT when they don't fit."""
    score = 0
    for given, need in ((key_types, idiom["data"].get("keys", [])), (value_types, idiom["data"].get("values", []))):
        if given is None:
            continue
        if len(given) < len(need):
            return NO_FIT
        for n, g in zip(need, given):
            steps = substitution_steps(n["type"], g, vocab)
            if steps is None:
                return NO_FIT
            score += steps
    return score


def draws_intervals(idiom: dict) -> bool:
    return idiom["data"].get("intervals") is True


def candidates(catalogue: dict, vocab: dict, task: str, shape: str | None = None, key_types: list | None = None,
               value_types: list | None = None, medium: str = "static",
               intervals: bool = False) -> list[tuple[dict, bool]]:
    """(idiom, lists the task) pairs, best first: shape match, then (with intervals) idioms that draw
    intervals, then type fit (fewest substitution steps), then catalogue order. With fewer than three that
    list the task, shape matches that don't are added, up to three."""
    pool = [i for i in catalogue.values() if medium == "any" or medium in i["medium"]]
    position = {iid: n for n, iid in enumerate(catalogue)}

    def order(i: dict) -> tuple:
        return (shape is not None and i["shape"] != shape, intervals and not draws_intervals(i),
                type_fit(i, key_types, value_types, vocab), position[i["id"]])

    listed = sorted((i for i in pool if task in i["tasks"]), key=order)
    extra = []
    if len(listed) < 3 and shape is not None:
        extra = sorted((i for i in pool if task not in i["tasks"] and i["shape"] == shape), key=order)
        extra = extra[:3 - len(listed)]
    return [(i, True) for i in listed] + [(i, False) for i in extra]


def describe(idiom: dict, lists_task: bool, shape_fits: bool = True, types_fit: bool = True,
             intervals_fit: bool = True) -> str:
    varying = (idiom.get("channels") or {}).get("varying")
    if varying is None:
        shown = "not stated"
    else:
        shown = ", ".join(c["channel"] + (f" ({c['where']})" if c.get("where") else "") for c in varying) or "none"
    parts = [f"{idiom['id']}: {idiom['name']}", f"hides: {first_sentence(idiom['_body'].get('Hides', ''))}",
             f"scale: {idiom['scale'].get('note') or 'not stated'}", f"varying: {shown}"]
    if idiom["origin"] == "kit":
        parts.append("kit idiom")
    elif idiom["origin"] == "own":
        parts.append("your idiom")
    if not lists_task:
        parts.append("doesn't list this task")
    if not shape_fits:
        parts.append("shape differs")
    if not types_fit:
        parts.append("types don't fit")
    if not intervals_fit:
        parts.append("draws no intervals")
    return " | ".join(parts)


def _figure_of(path: Path, project: Path, spec: dict | None) -> str:
    if spec is not None and isinstance(spec.get("figure"), str):
        return spec["figure"]
    return path.parent.name if path.parent != project / SPEC_DIR else path.stem


def cmd_check(project: Path, wanted: list[str], draft: bool) -> int:
    vocab = load_vocabulary()
    catalogue = load_catalogue(vocab)
    entries = []
    for path in spec_paths(project):
        try:
            entries.append((path, read_spec(path), None))
        except KitError as e:
            entries.append((path, None, str(e)))
    if wanted:
        known = {_figure_of(p, project, s) for p, s, _ in entries}
        missing = sorted(set(wanted) - known)
        if missing:
            raise KitError(f"no spec for {', '.join(missing)} in {SPEC_DIR}/")
        entries = [e for e in entries if _figure_of(e[0], project, e[1]) in wanted]
    if not entries:
        print(f"figures: no figure specs in {SPEC_DIR}/")
        return 0
    counts = {"error": 0, "warning": 0, "accepted": 0}
    for path, spec, problem in entries:
        if spec is None:
            findings, name = [Finding("spec", "error", problem)], _figure_of(path, project, None)
        elif path.parent != project / SPEC_DIR and "panel" not in spec:
            findings, name = [Finding("spec", "error", f"a spec in {SPEC_DIR}/{path.parent.name}/ needs a panel "
                                      "field")], label(spec)
        else:
            how = spec.get("how") if isinstance(spec.get("how"), dict) else {}
            idiom = how.get("idiom")
            ctx = Context(catalogue.get(idiom) if isinstance(idiom, str) else None, catalogue, vocab, project, draft)
            findings, name = run_checks(spec, ctx), label(spec)
        for f in findings:
            print(f"{name}: {f.severity} {f.check}: {f.message}" + (f" [{f.attribute}]" if f.attribute else ""))
            counts[f.severity] += 1
    def plural(k: int, word: str) -> str:
        return f"{k} {word}{'' if k == 1 else 's'}"
    print(f"figures: {plural(len(entries), 'spec')}, {plural(counts['error'], 'error')}, "
          f"{plural(counts['warning'], 'warning')}, {counts['accepted']} accepted")
    return 1 if counts["error"] else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--project", type=Path, required=True)
    c.add_argument("--task", required=True)
    c.add_argument("--shape")
    c.add_argument("--key-types")
    c.add_argument("--value-types")
    c.add_argument("--intervals", action="store_true", help="the values carry intervals, as in an event study")
    c.add_argument("--medium", default="static", choices=("static", "interactive", "any"))
    k = sub.add_parser("check")
    k.add_argument("--project", type=Path, required=True)
    k.add_argument("--draft", action="store_true", help="skip the script and figure file checks")
    k.add_argument("figures", nargs="*")
    a = ap.parse_args(argv)
    try:
        project = find_project(a.project)
        if a.cmd == "check":
            return cmd_check(project, a.figures, a.draft)
        vocab = load_vocabulary()
        if a.task not in vocab["tasks"]:
            raise KitError(f"unknown task {a.task!r}; use {', '.join(vocab['tasks'])}")
        if a.shape is not None and a.shape not in vocab["shapes"]:
            raise KitError(f"unknown shape {a.shape!r}; use {', '.join(vocab['shapes'])}")
        key_types, value_types = _types(a.key_types, vocab), _types(a.value_types, vocab)
        found = candidates(load_catalogue(vocab), vocab, a.task, a.shape, key_types, value_types, a.medium,
                           a.intervals)
        lines = [describe(i, listed, a.shape is None or i["shape"] == a.shape,
                          type_fit(i, key_types, value_types, vocab) != NO_FIT,
                          not a.intervals or draws_intervals(i)) for i, listed in found]
        medium = "" if a.medium == "any" else f" for {a.medium} figures"
        print("\n".join(lines) or f"no idiom lists {a.task}{medium}")
        return 0
    except KitError as e:
        print(f"figures: ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
