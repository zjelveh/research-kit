#!/usr/bin/env python3
"""Compare state/CURRENT_STATE.md with its allotment of the hook budget (spec §5.1).

Exit: 0 within allotment, 1 over budget, 2 error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, in_effect, load_limits  # noqa: E402


def allotment(limits: dict, rules_bytes: int) -> int:
    if rules_bytes > limits["rules_cap_bytes"]:
        raise KitError(f"rules.md is {rules_bytes} bytes; cap is {limits['rules_cap_bytes']}")
    allot = limits["hook_budget_bytes"] - rules_bytes - limits["reserve_bytes"]
    if allot < limits["min_state_bytes"]:
        raise KitError(f"limits leave CURRENT_STATE only {allot} bytes (< {limits['min_state_bytes']}); "
                       "shorten the rules in effect (kit which rules) or change limits.yml")
    return allot


def state_report(project: Path, limits: dict, rules_bytes: int) -> tuple[int, int]:
    state = Path(project) / "state" / "CURRENT_STATE.md"
    if not state.is_file():
        raise KitError(f"{state}: file not found")
    return len(state.read_bytes()), allotment(limits, rules_bytes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        rules_path = in_effect("rules")[0]
        size, allot = state_report(a.project, load_limits(), len(rules_path.read_bytes()))
    except (KitError, OSError) as e:
        print(f"check_state_size: ERROR: {e}", file=sys.stderr)
        return 2
    ok = size <= allot
    print(f"CURRENT_STATE: {size} bytes; allotment {allot} bytes: {'ok' if ok else 'OVER BUDGET'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
