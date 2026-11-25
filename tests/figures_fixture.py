"""Fixture idioms, specs and catalogues for the figures tests. Made-up names only: this file is exported."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

import idioms

BODY = ("## Helps\nCompares values across levels (Layout p. 19).\n\n"
        "## Hides\nOur reading: nothing beyond the usual.\n\n## Arrange\nA list along one axis (Layout p. 19).\n")
VIEW_BODY = "## Helps\nShows several views.\n\n## Hides\nOur reading: little.\n\n## Views\nTwo views side by side.\n"

BASE_IDIOM = {
    "id": "fixture-bars", "name": "Fixture bars", "origin": "munzner", "group": "keys", "kind": "idiom",
    "form": "encoding", "medium": ["static"], "shape": "1-key",
    "data": {"keys": [{"type": "categorical"}], "values": [{"type": "quantitative"}], "optional": []},
    "tasks": ["compare-values"], "marks": [{"level": 1, "mark": "point"}],
    "channels": {"encoded": [{"channel": "length", "carries": "value"}], "uniform": [], "varying": [],
                 "inherited": []},
    "scale": {"note": None}, "see_also": [], "sources": ["Layout p. 19"],
}


def vocab() -> dict:
    return idioms.load_vocabulary()


def idiom_text(body: str = BODY, **fields) -> str:
    fm = copy.deepcopy(BASE_IDIOM)
    fm.update(fields)
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def write_idiom(folder: Path, body: str = BODY, **fields) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    idiom_id = fields.get("id", BASE_IDIOM["id"])
    path = folder / f"{idiom_id}.md"
    path.write_text(idiom_text(body, **fields), encoding="utf-8")
    return path


def catalogue(tmp_path: Path, *idiom_fields: dict) -> dict:
    """A catalogue of fixture idioms only (no kit idioms, no personal folder)."""
    kit = tmp_path / "kit-idioms"
    for fields in idiom_fields:
        write_idiom(kit, **fields)
    return idioms.load_catalogue(vocab(), kit_dir=kit, personal=tmp_path / "no-personal")


def spec(**over) -> dict:
    """A valid spec for fixture-bars: one categorical key on position, one quantitative value on length."""
    s = {"figure": "fig1", "script": "analysis/fig1.R", "title": "Estimate by group", "title_in": "image",
         "what": {"items": "one estimate per group", "n_items": 5,
                  "keys": [{"name": "group", "type": "categorical", "levels": 5}],
                  "values": [{"name": "estimate", "type": "quantitative"}]},
         "why": {"task": "compare-values", "message": "Group C has the largest estimate."},
         "how": {"idiom": "fixture-bars",
                 "encode": {"group": [{"channel": "position-common", "axis": "x"}],
                            "estimate": [{"channel": "length"}]}}}
    s.update(over)
    s["_path"] = Path("notes/figures/fig1.yml")
    return s
