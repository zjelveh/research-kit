"""Shared helpers for the real-environment tests. Skip conditions are markers resolved lazily by conftest,
so collecting with -m "not real_env" never runs Rscript."""
import functools
import shutil
import subprocess

import pytest

needs_renv = pytest.mark.needs_renv
needs_uv = pytest.mark.needs_uv
needs_latexmk = pytest.mark.needs_latexmk


def _rscript(code):
    return subprocess.run(["Rscript", "--no-init-file", "-e", code], capture_output=True, text=True)


@functools.lru_cache(maxsize=None)
def renv_available():
    return shutil.which("Rscript") is not None and _rscript('quit(status = !requireNamespace("renv", quietly = TRUE))').returncode == 0


@functools.lru_cache(maxsize=None)
def stray_user_packages():
    """Scratch packages that must never be in the user R library, or a test could pass vacuously."""
    if shutil.which("Rscript") is None:
        return ()
    r = _rscript('cat(Filter(function(p) nzchar(system.file(package = p)), c("demo", "onlyproj")))')
    return tuple(r.stdout.split())


CHECKS = {
    "needs_renv": (lambda: renv_available(), "renv not installed in the user R library"),
    "needs_uv": (lambda: shutil.which("uv") is not None, "uv not on the PATH"),
    "needs_latexmk": (lambda: shutil.which("latexmk") is not None, "latexmk not installed"),
}
