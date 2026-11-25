#!/usr/bin/env python3
"""The figures catalogue (figures spec section 2): the fixed vocabulary, idiom files, and the catalogue in
effect, which is the kit's idioms with the personal ones laid over them."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import DEFAULTS, PLUGIN_ROOT, VENUE_RE, KitError, personal_dir  # noqa: E402

VOCABULARY = PLUGIN_ROOT / "figures" / "vocabulary.yml"
KIT_IDIOMS = DEFAULTS / "idioms"
FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
SECTION_RE = re.compile(r"^## (.+?)\n(.*?)(?=^## |\Z)", re.S | re.M)
PAGES = r"pp?\. [0-9][0-9, –-]*"
CITE_RE = re.compile(rf"\(([^()]*?) {PAGES}\)")
SOURCE_RE = re.compile(rf"^(.+?) {PAGES}$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`])")
QUOTES = ('"', "“", "”")
REQUIRED = ("id", "name", "origin", "group", "kind", "form", "medium", "shape", "data", "tasks", "scale",
            "see_also", "sources")
SCALE_KEYS = ("items", "key_levels", "second_key_levels", "value_levels", "series", "attributes")
SPATIAL = ("regions", "points", "lines")
CHANNEL_LISTS = ("encoded", "uniform", "varying", "inherited")


def load_vocabulary(path: Path = VOCABULARY) -> dict:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise KitError(f"{path}: cannot read the vocabulary: {e}") from None
    if not isinstance(data, dict):
        raise KitError(f"{path}: the vocabulary must be a mapping")
    return data


def parse_idiom(path: Path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise KitError(f"{path}: cannot read: {e}") from None
    m = FRONT_RE.match(text)
    if not m:
        raise KitError(f"{path}: no YAML front matter between --- lines")
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise KitError(f"{path}: front matter is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise KitError(f"{path}: front matter must be a mapping")
    data["_path"] = path
    data["_body"] = {name.strip(): body.strip() for name, body in SECTION_RE.findall(m.group(2))}
    return data


def _term(value, allowed) -> bool:
    """value is text and one of allowed (a list or the keys of a mapping); lists in YAML never crash a lookup."""
    return isinstance(value, str) and value in allowed


def _one_of(value, allowed: list, what: str) -> list[str]:
    return [] if value in allowed else [f"{what} {value!r} is not one of: {', '.join(map(str, allowed))}"]


def slot_types(slot: dict) -> list:
    """The attribute types a data slot takes: its type, or its list of types."""
    t = slot.get("type")
    return list(t) if isinstance(t, list) else [t]


def _slot_ok(entry, key: str, types: list) -> bool:
    """One attribute type; an optional slot may list several."""
    if not isinstance(entry, dict):
        return False
    t = entry.get("type")
    if key == "optional" and isinstance(t, list):
        return bool(t) and all(_term(x, types) for x in t)
    return _term(t, types)


def _check_data(data, vocab: dict) -> list[str]:
    if not isinstance(data, dict):
        return ["data must be a mapping"]
    p, types = [], vocab["attribute_types"]
    unknown = set(data) - {"keys", "values", "optional", "spatial", "intervals"}
    if unknown:
        p.append(f"data has unknown fields: {', '.join(sorted(unknown))}")
    for key in ("keys", "values", "optional"):
        entries = data.get(key, [])
        if not isinstance(entries, list) or not all(_slot_ok(e, key, types) for e in entries):
            several = " (an optional slot may list several)" if key == "optional" else ""
            p.append(f"data.{key} must be a list of entries with a type from: {', '.join(types)}{several}")
            continue
        allowed = {"type", "channel", "repeats"} if key == "optional" else {"type", "repeats"}
        extra = sorted({f for e in entries for f in e} - allowed)
        if extra:
            p.append(f"data.{key}: unknown fields: {', '.join(extra)}")
        if any(not isinstance(e.get("repeats", False), bool) for e in entries):
            p.append(f"data.{key}: repeats must be true or false")
        elif key != "optional" and any(e.get("repeats") for e in entries[:-1]):
            p.append(f"data.{key}: only the last entry may repeat")
        if key == "optional" and any(not _term(e.get("channel", "hue"), vocab["channels"]) for e in entries):
            p.append("data.optional: a channel must be in the vocabulary")
    if not isinstance(data.get("intervals", False), bool):
        p.append("data.intervals must be true or false")
    if "spatial" in data and data["spatial"] not in SPATIAL:
        p.append(f"data.spatial must be one of: {', '.join(SPATIAL)}")
    return p


def _check_marks(marks, vocab: dict) -> list[str]:
    ok = isinstance(marks, list) and marks and all(
        isinstance(m, dict) and set(m) == {"level", "mark"} and isinstance(m["level"], int)
        and not isinstance(m["level"], bool) and m["level"] >= 1 and m["mark"] in vocab["marks"] for m in marks)
    return [] if ok else [f"marks must be a non-empty list of {{level, mark}}, mark from: {', '.join(vocab['marks'])}"]


def _check_channels(channels, vocab: dict) -> list[str]:
    if not isinstance(channels, dict) or set(channels) != set(CHANNEL_LISTS):
        return [f"channels must have exactly: {', '.join(CHANNEL_LISTS)}"]
    p = []
    for key in CHANNEL_LISTS:
        entries = channels[key]
        if entries is None:
            continue                                    # null: Munzner doesn't say
        allowed = {"channel", "carries", "where"} if key == "encoded" else {"channel", "where"}
        if not isinstance(entries, list):
            p.append(f"channels.{key} must be a list or null")
            continue
        for e in entries:
            if not isinstance(e, dict) or set(e) - allowed or not _term(e.get("channel"), vocab["channels"]):
                p.append(f"channels.{key}: {e!r} needs a vocabulary channel and only {', '.join(sorted(allowed))}")
            elif key == "encoded" and not isinstance(e.get("carries"), str):
                p.append(f"channels.encoded: {e['channel']} needs carries")
    return p


def _check_scale(scale) -> list[str]:
    if not isinstance(scale, dict) or "note" not in scale:
        return ["scale must be a mapping with a note (text, or null when Munzner doesn't say)"]
    p = []
    if scale["note"] is not None and not isinstance(scale["note"], str):
        p.append("scale.note must be text or null")
    for key, bound in scale.items():
        if key == "note":
            continue
        if key not in SCALE_KEYS:
            p.append(f"scale.{key} is not one of: {', '.join(SCALE_KEYS)}")
        elif not (isinstance(bound, dict) and len(bound) == 1 and set(bound) <= {"max", "min"}
                  and isinstance(next(iter(bound.values())), int)):
            p.append(f"scale.{key} must be {{max: N}} or {{min: N}}")
    return p


def _check_see_also(see_also) -> list[str]:
    ok = isinstance(see_also, list) and all(
        isinstance(s, dict) and set(s) == {"id", "when"} and isinstance(s["id"], str) and isinstance(s["when"], str)
        for s in see_also)
    return [] if ok else ["see_also must be a list of {id, when}"]


def _check_sources(idiom: dict, vocab: dict) -> list[str]:
    sources = idiom["sources"]
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        return ["sources must be a list of citations such as Layout p. 19"]
    if not sources and idiom["origin"] == "munzner":
        return ["sources may be empty only for origin: kit or own"]
    bad = [s for s in sources if not (m := SOURCE_RE.match(s)) or m.group(1) not in vocab["decks"]]
    return [f"sources must name known decks ({', '.join(vocab['decks'])}): {', '.join(bad)}"] if bad else []


def _check_body(idiom: dict, vocab: dict) -> list[str]:
    body = idiom["_body"]
    needed = ("Helps", "Hides", "Views" if idiom.get("form") == "view" else "Arrange")
    p = [f"body needs a ## {s} section with text" for s in needed if not body.get(s)]
    text = "\n".join(body.values())
    if any(q in text for q in QUOTES):
        p.append("body has a quotation mark; restate in the kit's words instead of quoting")
    unknown = sorted({d for d in CITE_RE.findall(text) if d not in vocab["decks"]})
    if unknown:
        p.append(f"body cites unknown decks: {', '.join(unknown)}")
    return p


def validate_idiom(idiom: dict, vocab: dict) -> list[str]:
    """Every problem with one idiom file, or [] (see_also ids are checked against the whole catalogue)."""
    missing = [k for k in REQUIRED if k not in idiom]
    if missing:
        return [f"missing fields: {', '.join(missing)}"]
    p = []
    if not isinstance(idiom["id"], str) or idiom["id"] != idiom["_path"].stem or not VENUE_RE.fullmatch(idiom["id"]):
        p.append(f"id {idiom['id']!r} must match the file name and use lowercase letters, digits, - and _")
    if not isinstance(idiom["name"], str) or not idiom["name"].strip():
        p.append("name must be text")
    if "order" in idiom and not (isinstance(idiom["order"], int) and not isinstance(idiom["order"], bool)
                                 and idiom["order"] >= 1):
        p.append("order must be a whole number of at least 1")
    for key, allowed in (("origin", "origins"), ("group", "groups"), ("kind", "kinds"), ("form", "forms"),
                         ("shape", "shapes")):
        p += _one_of(idiom[key], vocab[allowed], key)
    for key, allowed in (("medium", "media"), ("tasks", "tasks")):
        v = idiom[key]
        if not isinstance(v, list) or not v or any(x not in vocab[allowed] for x in v):
            p.append(f"{key} must be a non-empty list from: {', '.join(vocab[allowed])}")
    p += _check_data(idiom["data"], vocab)
    if idiom["form"] == "view":
        if idiom.get("channels") is not None:
            p.append("a view idiom has channels: null")
        for key in ("changes", "fixed"):
            if not isinstance(idiom.get(key), str) or not idiom[key].strip():
                p.append(f"a view idiom needs {key} as text")
    else:
        p += _check_marks(idiom.get("marks"), vocab) + _check_channels(idiom.get("channels"), vocab)
    return p + _check_scale(idiom["scale"]) + _check_see_also(idiom["see_also"]) + \
        _check_sources(idiom, vocab) + _check_body(idiom, vocab)


def load_catalogue(vocab: dict, kit_dir: Path | None = None, personal: Path | None = None) -> dict[str, dict]:
    """The catalogue in effect: the union by id, a personal file winning, sorted by order (idioms without one
    last, the kit's before personal additions), then group order, then id. Stops at the first invalid file,
    naming it."""
    kit_dir = KIT_IDIOMS if kit_dir is None else Path(kit_dir)
    personal = personal_dir() / "idioms" if personal is None else Path(personal)
    found: dict[str, dict] = {}
    kit_ids = set()
    for source, folder in (("default", kit_dir), ("personal", personal)):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            idiom = parse_idiom(path)
            problems = validate_idiom(idiom, vocab)
            if problems:
                raise KitError(f"{path}: " + "; ".join(problems))
            idiom["_source"] = source
            if source == "default":
                kit_ids.add(idiom["id"])
            found[idiom["id"]] = idiom
    for idiom in found.values():
        unknown = [s["id"] for s in idiom["see_also"] if s["id"] not in found]
        if unknown:
            raise KitError(f"{idiom['_path']}: see_also names idioms not in the catalogue: {', '.join(unknown)}")
    groups = vocab["groups"]
    ordered = sorted(found.values(), key=lambda i: ("order" not in i, i.get("order", 0), i["id"] not in kit_ids,
                                                    groups.index(i["group"]), i["id"]))
    return {i["id"]: i for i in ordered}


def first_sentence(text: str) -> str:
    """The first sentence of a body section; page abbreviations (p. 25) don't end a sentence."""
    return SENTENCE_END.split(text.strip(), maxsplit=1)[0] if text.strip() else ""
