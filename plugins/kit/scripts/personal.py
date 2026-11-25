#!/usr/bin/env python3
"""The personal layer (shareable-kit spec §2).

  personal.py which <item>        print the file in effect
  personal.py customize <item>    copy the default (or, for a new venue or idiom, a template) into the personal folder
  personal.py where                                                  print the personal folder
  <item> is rules, writing-voice, writing-patterns, slides-style, figure-style, venue <name> or idiom <name>

Exit: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import DEFAULTS, PLUGIN_ROOT, KitError, in_effect, item_rel, personal_dir  # noqa: E402

VENUE_TEMPLATE = PLUGIN_ROOT / "templates" / "venue.md"
IDIOM_TEMPLATE = PLUGIN_ROOT / "templates" / "idiom.md"


def customize(item: str, name: str | None = None) -> Path:
    rel = item_rel(item, name)
    target = personal_dir() / rel
    if target.exists():
        raise KitError(f"{target} already exists; edit it there")
    if (DEFAULTS / rel).is_file():
        text = (DEFAULTS / rel).read_text(encoding="utf-8")
    elif item == "venue":
        text = VENUE_TEMPLATE.read_text(encoding="utf-8").replace("{{VENUE}}", name)
    elif item == "idiom":
        text = IDIOM_TEMPLATE.read_text(encoding="utf-8").replace("{{ID}}", name)
    else:
        raise KitError(f"the kit has no default {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:                                        # write whole, then link: never a partial file, never an overwrite
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            os.link(tmp, target)
        except FileExistsError:
            raise KitError(f"{target} already exists; edit it there") from None
    finally:
        os.unlink(tmp)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("which", "customize", "where"))
    ap.add_argument("item", nargs="?")
    ap.add_argument("name", nargs="?")
    a = ap.parse_args(argv)
    try:
        if a.action == "where":
            print(personal_dir())
        elif a.item is None:
            raise KitError(f"{a.action} needs an item: rules, writing-voice, writing-patterns, slides-style, "
                           "figure-style, venue <name> or idiom <name>")
        elif a.action == "which":
            print(in_effect(a.item, a.name)[0])
        else:
            print(customize(a.item, a.name))
    except (KitError, OSError) as e:
        print(f"personal: ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
