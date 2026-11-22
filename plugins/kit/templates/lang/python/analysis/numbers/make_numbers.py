"""Computes the paper's numbers that come from Python.

numbers_build.py runs this script and writes the macros and the ledger (research-kit languages
spec §5). Running it directly stops with an error.
Run: "{{KIT}}" numbers_build.py --project .
"""
import importlib.util
import os

_emit = os.environ.get("KIT_NUMBERS_EMIT")
if not _emit:
    raise SystemExit("run this script through numbers_build.py, which sets KIT_NUMBERS_EMIT")
_spec = importlib.util.spec_from_file_location("numbers_emit", _emit)
numbers_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers_emit)

entries = [
    # dict(name="biasMain", value=float(summary["bias"][0]), format="%.3f",
    #      src="analysis/sims/summary.csv"),
]

numbers_emit.emit_numbers(entries)
