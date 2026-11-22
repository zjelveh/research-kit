import os
import sys
from pathlib import Path


def test_tests_never_see_the_users_personal_layer_or_stable_path(tmp_path):
    for var in ("KIT_PERSONAL_DIR", "KIT_DATA_DIR", "KIT_VENV"):
        assert os.environ.get(var), f"{var} not set by conftest"
    home = Path.home()
    assert not Path(os.environ["KIT_PERSONAL_DIR"]).is_relative_to(home / ".config")
    data = Path(os.environ["KIT_DATA_DIR"])
    assert not data.is_relative_to(home / ".local")
    assert (data / "plugin" / "bin").resolve().parent.name == "kit"
    assert Path(os.environ["KIT_VENV"]) == Path(sys.prefix)
