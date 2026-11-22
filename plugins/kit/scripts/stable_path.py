#!/usr/bin/env python3
"""Point the stable path at this plugin (shareable-kit spec §3); `kit setup` runs it. Exit 0 ok, 2 error."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import PLUGIN_ROOT, KitError, data_dir, link_stable  # noqa: E402


def main() -> int:
    try:
        link_stable()
    except (KitError, OSError) as e:
        print(f"kit setup: ERROR: {e}", file=sys.stderr)
        return 2
    print(f"research-kit: environment ready; {data_dir() / 'plugin'} -> {PLUGIN_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
