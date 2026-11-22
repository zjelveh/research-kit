#!/usr/bin/env bash
# Create .venv, the development environment for the tests (pytest and PyYAML).
# The kit's runtime environment is separate: plugins/kit/bin/kit setup creates it.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${KIT_PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 12), f"need Python >= 3.12, got {sys.version}"'
"$PY" -m venv "$KIT/.venv"
"$KIT/.venv/bin/pip" install --quiet --upgrade pip
"$KIT/.venv/bin/pip" install --quiet -r "$KIT/requirements.txt"
"$KIT/.venv/bin/python" -c 'import yaml, pytest; print("venv ok: PyYAML", yaml.__version__, "pytest", pytest.__version__)'
