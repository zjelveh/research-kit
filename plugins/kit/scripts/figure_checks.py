"""Checks on figure specs (figures spec section 4). Each check takes a spec and a Context and returns
Findings. CHECKS lists them in the order they run; the first, check_spec, stops the rest when it finds an
error. Adding a check is one function, one entry in CHECKS and one test."""
from __future__ import annotations

import datetime as dt
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_spec import attributes, base, channel_kind, channel_name, figure_file, fits, focus  # noqa: E402
from idioms import slot_types  # noqa: E402
from kitlib import KitError  # noqa: E402


@dataclass
class Finding:
    check: str
    severity: str                # error, warning, or accepted: a warning the spec accepts
    message: str
    attribute: str | None = None


@dataclass
class Context:
    idiom: dict | None           # the idiom in effect, or None for idiom: none or an unknown idiom
    catalogue: dict
    vocab: dict
    project: Path
    draft: bool = False


DATE_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?")
AXES = ("x", "y")
SPATIAL = ("regions", "points", "lines")
COLOUR = {"colour", "hue", "luminance", "saturation"}      # an optional slot on colour takes any of these


def _number(v, low: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= low


def _term(value, allowed) -> bool:
    return isinstance(value, str) and value in allowed


def _position(v) -> bool:
    """A reference mark's position: a number, or a date (YAML reads 2020-01-01 as a date) or year-month."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)) or isinstance(v, dt.date) \
        or (isinstance(v, str) and DATE_RE.fullmatch(v) is not None)


def _check_references(refs, vocab: dict, err) -> None:
    if not isinstance(refs, list):
        err("how.reference must be a list")
        return
    for r in refs:
        if not isinstance(r, dict) or r.get("kind") not in vocab["reference_kinds"] \
                or r.get("axis") not in vocab["reference_axes"]:
            err(f"a reference needs kind ({', '.join(vocab['reference_kinds'])}) and axis "
                f"({', '.join(vocab['reference_axes'])})")
            continue
        if not isinstance(r.get("meaning"), str) or not r["meaning"].strip():
            err("each reference mark needs its meaning, such as no effect or treatment date")
        if r["kind"] == "line" and r["axis"] != "diagonal" and "at" not in r:
            err("a reference line needs at, except on the diagonal")
        if r["kind"] == "band" and not ("from" in r and "to" in r):
            err("a reference band needs from and to")
        if any(k in r and not _position(r[k]) for k in ("at", "from", "to")):
            err("a reference position must be a number or a date (YYYY-MM or YYYY-MM-DD)")
        if r.get("label_in", "image") not in ("image", "caption"):
            err("a reference's label_in must be image or caption")


def check_spec(spec: dict, ctx: Context) -> list[Finding]:
    v, out = ctx.vocab, []

    def err(message: str, attribute: str | None = None) -> None:
        out.append(Finding("spec", "error", message, attribute))

    for key in ("figure", "script", "title", "what", "why", "how"):
        if key not in spec:
            err(f"missing field: {key}")
    for key in ("figure", "script", "title", "file", "panel"):
        if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
            err(f"{key} must be non-empty text")
    if not out and any(c in spec["figure"] for c in "/\\*?["):
        err("figure is the figure's file name without folder or extension, such as effect_by_year")
    if out:
        return out
    what, why, how = spec["what"], spec["why"], spec["how"]
    if not all(isinstance(x, dict) for x in (what, why, how)):
        err("what, why and how must each be a mapping of fields")
        return out
    if spec.get("title_in", "image") not in ("image", "caption"):
        err("title_in must be image or caption")
    if not isinstance(what.get("items"), str):
        err("what.items must say what one item is")
    if not _number(what.get("n_items"), 0):
        err("what.n_items must be the number of marks drawn, a whole number")
    if "spatial" in what and what["spatial"] not in SPATIAL:
        err(f"what.spatial must be one of: {', '.join(SPATIAL)}")
    names = []
    for field in ("keys", "values"):
        entries = what.get(field, [])
        if not isinstance(entries, list):
            err(f"what.{field} must be a list")
            continue
        for e in entries:
            if not isinstance(e, dict) or not isinstance(e.get("name"), str):
                err(f"what.{field}: each entry needs a name")
                continue
            names.append(e["name"])
            if e.get("type") not in v["attribute_types"]:
                err(f"type {e.get('type')!r} is not one of: {', '.join(v['attribute_types'])}", e["name"])
            if "role" in e and e["role"] not in v["roles"]:
                err(f"role {e['role']!r} is not one of: {', '.join(v['roles'])}", e["name"])
            if "levels" in e and not _number(e["levels"], 1):
                err("levels must be a whole number of at least 1", e["name"])
    if len(names) != len(set(names)):
        err("attribute names must be unique")
    if why.get("task") not in v["tasks"]:
        err(f"why.task {why.get('task')!r} is not one of: {', '.join(v['tasks'])}")
    if not isinstance(why.get("message"), str) or not why["message"].strip():
        err("why.message must say what the reader should see")
    f = why.get("focus")
    if f is not None and not (isinstance(f, str) and f in names) \
            and not (isinstance(f, dict) and isinstance(f.get("derived"), str)):
        err("why.focus must name an attribute, or be {derived: <what>}")
    idiom = how.get("idiom")
    if idiom != "none" and not (isinstance(idiom, str) and idiom in ctx.catalogue):
        err(f"unknown idiom {idiom!r}; figures.py candidates lists the ones that fit")
    encode = how.get("encode", {})
    if not isinstance(encode, dict):
        err("how.encode must map attribute names to lists of channels")
    else:
        for name, entries in encode.items():
            if name not in names:
                err("how.encode names an unknown attribute", name)
            elif not isinstance(entries, list) or not entries:
                err("an attribute's encode entry is a non-empty list of channels", name)
            else:
                for e in entries:
                    if not isinstance(e, dict) or not _term(e.get("channel"), v["channels"]):
                        err(f"channel {e.get('channel') if isinstance(e, dict) else e!r} is not in the vocabulary",
                            name)
                    elif e["channel"] == "colour" and not _term(e.get("colour_scale"), v["colour_scales"]):
                        err("colour needs colour_scale: categorical, sequential or diverging", name)
                    elif "axis" in e and e["axis"] not in AXES:
                        err("an encode entry's axis must be x or y", name)
    if "facet" in how:
        faceted = [a["name"] for a in attributes(spec) if a["kind"] == "key" and a.get("role") == "facet"]
        facet = how["facet"]
        if not isinstance(facet, dict) or facet.get("by") not in faceted:
            err("how.facet.by must name a key with role: facet")
        elif facet.get("scales", "shared") not in ("shared", "free"):
            err("how.facet.scales must be shared or free")
    if "reference" in how:
        _check_references(how["reference"], v, err)
    accepted = spec.get("accepted", [])
    if not isinstance(accepted, list) or not all(isinstance(a, dict) and isinstance(a.get("check"), str)
                                                 and isinstance(a.get("reason"), str) for a in accepted):
        err("accepted must be a list of {check, attribute (optional), reason}")
    if not ctx.draft:
        if not (ctx.project / str(spec["script"])).is_file():
            err(f"script not found: {spec['script']}")
        try:
            if figure_file(ctx.project, spec) is None:
                err(f"figure file not found for {spec['figure']}")
        except KitError as e:
            err(str(e))
    return out


def check_data_fit(spec: dict, ctx: Context) -> list[Finding]:
    idiom = ctx.idiom
    if idiom is None or idiom["form"] != "encoding":
        return []
    data, out = idiom["data"], []
    optional = list(data.get("optional", []))   # an optional slot takes exactly its type, or one of its types
    encode = spec["how"].get("encode", {})

    def on_channels(name: str) -> set:
        entries = encode.get(name, [])
        found = {e["channel"] for e in entries} | {channel_name(e, ctx.vocab) for e in entries}
        return found | ({"colour"} if found & COLOUR else set())
    for kind, field in (("key", "keys"), ("value", "values")):
        need, given = data.get(field, []), base(spec, kind)
        if len(given) < len(need):
            out.append(Finding("data-fit", "error",
                               f"{idiom['id']} needs {len(need)} {field}; the spec has {len(given)} without a role"))
            continue
        for n, g in zip(need, given):
            if not fits(n["type"], g["type"], ctx.vocab):
                out.append(Finding("data-fit", "warning", f"{g['type']} where {idiom['id']} expects {n['type']}",
                                   g["name"]))
        rest = given[len(need):]
        if need and need[-1].get("repeats"):          # the last slot also takes the extras that fit it
            rest = [g for g in rest if not fits(need[-1]["type"], g["type"], ctx.vocab)]
        for g in rest:
            match = next((o for o in optional if g["type"] in slot_types(o)
                          and ("channel" not in o or o["channel"] in on_channels(g["name"]))), None)
            if match is None:
                out.append(Finding("data-fit", "warning", f"not part of {idiom['id']}: give it a role (interval, "
                                   "facet, layer) or choose another idiom", g["name"]))
            elif not match.get("repeats"):
                optional.remove(match)
    return out


def check_task(spec: dict, ctx: Context) -> list[Finding]:
    idiom, task = ctx.idiom, spec["why"]["task"]
    if idiom is None or task in idiom["tasks"]:
        return []
    see = [s["id"] for s in idiom["see_also"] if task in ctx.catalogue[s["id"]]["tasks"]]
    others = [i for i, d in ctx.catalogue.items() if task in d["tasks"] and i not in see and i != idiom["id"]]
    alternatives = see + others[:max(0, 3 - len(see))]
    message = f"{idiom['id']} doesn't list the task {task}"
    if alternatives:
        message += f"; idioms that do: {', '.join(alternatives)}"
    return [Finding("task", "warning", message)]


def check_expressiveness(spec: dict, ctx: Context) -> list[Finding]:
    """Marks p. 9: ordered attributes on magnitude channels, categorical ones on identity channels.
    Position suits both, so keys placed along an axis are arrangement and never flagged."""
    out, f = [], focus(spec)
    by_name = {a["name"]: a for a in attributes(spec)}
    for name, entries in spec["how"].get("encode", {}).items():
        a = by_name[name]
        for e in entries:
            kind, _ = channel_kind(e, ctx.vocab)
            shown = e["channel"] if e["channel"] != "colour" else f"colour ({e['colour_scale']})"
            if kind == "magnitude" and a["type"] == "categorical":
                out.append(Finding("expressiveness", "error",
                                   f"categorical attribute on {shown}, a magnitude channel (Marks p. 9)", name))
            elif kind == "identity" and a["type"] in ("ordinal", "quantitative"):
                out.append(Finding("expressiveness", "error" if name == f else "warning",
                                   f"{a['type']} attribute on {shown}, an identity channel that shows no order "
                                   "(Marks p. 9)", name))
    return out


def check_effectiveness(spec: dict, ctx: Context) -> list[Finding]:
    """The focus should have the best-ranked channel among those carrying values (Marks p. 9)."""
    f = focus(spec)
    by_name = {a["name"]: a for a in attributes(spec)}
    if f is None or by_name.get(f, {}).get("type") == "categorical":
        return []                                  # a categorical focus belongs on an identity channel
    encode = spec["how"].get("encode", {})

    def ranked(name: str) -> list[tuple[int, str]]:
        found = []
        for e in encode.get(name, []):
            kind, rank = channel_kind(e, ctx.vocab)
            if kind in ("position", "magnitude") and rank is not None:
                found.append((rank, e["channel"]))
        return found

    mine = ranked(f)
    if not mine:
        return [Finding("effectiveness", "warning", "the focus is on no ranked position or magnitude channel", f)]
    best = min(mine)
    others = [(r, ch, a["name"]) for a in base(spec, "value") if a["name"] != f for r, ch in ranked(a["name"])]
    better = [o for o in others if o[0] < best[0]]
    if not better:
        return []
    rank, channel, name = min(better)
    return [Finding("effectiveness", "warning", f"the focus is on {best[1]} (rank {best[0]}) while {name} has "
                    f"{channel} (rank {rank}); the task's attribute should get the best channel (Marks p. 9)", f)]


def check_scale(spec: dict, ctx: Context) -> list[Finding]:
    idiom = ctx.idiom
    if idiom is None:
        return []
    keys, values = base(spec, "key"), base(spec, "value")
    counts = {
        "items": spec["what"].get("n_items"),
        "key_levels": keys[0].get("levels") if keys else None,
        "second_key_levels": keys[1].get("levels") if len(keys) > 1 else None,
        "value_levels": max((a["levels"] for a in values if a.get("levels")), default=None),
        "series": max((a["levels"] for a in attributes(spec) if a.get("role") == "layer" and a.get("levels")),
                      default=None),
        "attributes": len(values) or None,
    }
    note = idiom["scale"].get("note")
    alternatives = ", ".join(s["id"] for s in idiom["see_also"])
    advice = f"; consider {alternatives + ', ' if alternatives else ''}aggregating, or small multiples"
    out = []
    for key, bound in idiom["scale"].items():
        n = counts.get(key)
        if key == "note" or n is None:
            continue
        for side, word, broken in (("max", "above", lambda b: n > b), ("min", "below", lambda b: n < b)):
            if side in bound and broken(bound[side]):
                out.append(Finding("scale", "warning", f"{key} {n} is {word} {idiom['id']}'s {bound[side]}"
                                   + (f" ({note})" if note else "") + advice))
    return out


CHECKS = [check_spec, check_data_fit, check_task, check_expressiveness, check_effectiveness, check_scale]


def run_checks(spec: dict, ctx: Context) -> list[Finding]:
    """Every check in order, stopping after check_spec if it finds an error. A warning matching an
    `accepted` entry (same check, and same attribute when one is given) becomes `accepted`."""
    findings = CHECKS[0](spec, ctx)
    if any(f.severity == "error" for f in findings):
        return findings
    for check in CHECKS[1:]:
        findings += check(spec, ctx)
    accepted = spec.get("accepted") or []
    for f in findings:
        if f.severity == "warning" and any(a["check"] == f.check and a.get("attribute") in (None, f.attribute)
                                           for a in accepted):
            f.severity = "accepted"
    return findings
