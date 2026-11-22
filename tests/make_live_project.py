#!/usr/bin/env python3
"""Create a scaffolded, attached, pushed project for live `claude -p` checks.

Usage: make_live_project.py ROOT NAME   (prints the project path)
"""
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT / "plugins" / "kit" / "scripts"), str(KIT / "tests")]
from build_fixture import bare_overleaf  # noqa: E402
from scaffold import cmd_attach, cmd_new  # noqa: E402

from check_state_size import allotment  # noqa: E402
from kitlib import in_effect, load_limits  # noqa: E402

root, name = Path(sys.argv[1]), sys.argv[2]
bare = bare_overleaf(root, {"main.tex": "\\documentclass{article}\n\\begin{document}\nHi.\n\\end{document}\n"})
p = cmd_new(name, root, ["r"])
cmd_attach(str(bare), p)
subprocess.run(["git", "-C", str(p / "paper"), "push", "-q", "origin", "main"], check=True)
# Pad CURRENT_STATE to just under its allotment so the live check tests the real budget end to end.
state = p / "state" / "CURRENT_STATE.md"
allot = allotment(load_limits(), len(in_effect("rules")[0].read_bytes()))
tail = "\nLAST-LINE-CHECK-7Q2\n"
body = state.read_text() + "\n## Padding\n"
pad = allot - 64 - len(body.encode()) - len(tail.encode())
body += "".join(f"pad line {k:05d} {'x' * 60}\n" for k in range(max(0, pad) // 77))
state.write_text(body + tail)
print(f"CURRENT_STATE {len(state.read_bytes())} bytes; allotment {allot}", file=sys.stderr)
print(p)
