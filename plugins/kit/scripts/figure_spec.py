"""Figure specs (figures spec section 3): notes/figures/<figure>.yml, or notes/figures/<figure>/<panel>.yml
for a composite. Reading them, and what the checks derive from them."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, load_config, paper_folders  # noqa: E402

SPEC_DIR = Path("notes") / "figures"


def spec_paths(project: Path) -> list[Path]:
    folder = project / SPEC_DIR
    return sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")]) + \
        sorted([*folder.glob("*/*.yml"), *folder.glob("*/*.yaml")])


def read_spec(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise KitError(f"cannot read {path.name}: {e}") from None
    if not isinstance(data, dict):
        raise KitError(f"{path.name} must be a mapping of fields")
    data["_path"] = path
    return data


def label(spec: dict) -> str:
    figure = spec.get("figure") or spec["_path"].stem
    return f"{figure}/{spec['panel']}" if spec.get("panel") else str(figure)


def attributes(spec: dict) -> list[dict]:
    """Keys, then values: each entry with its kind ('key' or 'value') added."""
    what = spec.get("what") if isinstance(spec.get("what"), dict) else {}
    return [{**e, "kind": kind} for kind, field in (("key", "keys"), ("value", "values"))
            for e in (what.get(field) or []) if isinstance(e, dict)]


def base(spec: dict, kind: str) -> list[dict]:
    """The keys or values the base layout uses: those without a role."""
    return [a for a in attributes(spec) if a["kind"] == kind and not a.get("role")]


def shape(spec: dict) -> str | None:
    what = spec.get("what") if isinstance(spec.get("what"), dict) else {}
    if what.get("spatial"):
        return "geographic"
    return {0: "0-keys", 1: "1-key", 2: "2-keys"}.get(len(base(spec, "key")))


def substitution_steps(needed: str, given: str, vocab: dict) -> int | None:
    """0 when the types match; n when `given` stands in for `needed` as its n-th substitute (the rules chain,
    so quantitative reaches categorical in two steps); None when it can't."""
    if given == needed:
        return 0
    chain = vocab["substitutes"].get(given, [])
    return chain.index(needed) + 1 if needed in chain else None


def fits(needed: str, given: str, vocab: dict) -> bool:
    """Can an attribute of type `given` stand where `needed` is expected?"""
    return substitution_steps(needed, given, vocab) is not None


def focus(spec: dict) -> str | None:
    """The attribute the task is about: why.focus, or the first value without a role. None when derived."""
    f = (spec.get("why") or {}).get("focus")
    if isinstance(f, dict):
        return None
    if isinstance(f, str):
        return f
    values = base(spec, "value")
    return values[0]["name"] if values else None


def channel_kind(entry: dict, vocab: dict) -> tuple[str | None, int | None]:
    """(type, rank) of one encode entry. Colour takes its colour scale's."""
    if entry.get("channel") == "colour":
        scale = vocab["colour_scales"].get(entry.get("colour_scale"), {})
        return scale.get("type"), scale.get("rank")
    channel = vocab["channels"].get(entry.get("channel"), {})
    return channel.get("type"), channel.get("rank")


def channel_name(entry: dict, vocab: dict) -> str | None:
    """The channel an encode entry uses; colour counts as the channel its colour scale acts as (hue or luminance)."""
    if entry.get("channel") == "colour":
        return vocab["colour_scales"].get(entry.get("colour_scale"), {}).get("channel")
    return entry.get("channel")


def figure_file(project: Path, spec: dict) -> Path | None:
    """The figure's file: `file` when given, else <figure>.* in the paper's figures folder."""
    if spec.get("file"):
        path = project / spec["file"]
        return path if path.exists() else None
    cfg = load_config(project)
    paper = (project / cfg["paper_dir"]).resolve()
    folder = paper_folders(project, cfg, paper)[-2]
    hits = sorted(p for p in folder.iterdir() if p.is_file() and p.stem == spec["figure"]) if folder.is_dir() else []
    return hits[0] if hits else None
