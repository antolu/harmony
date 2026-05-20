from __future__ import annotations

import pathlib


def test_internal_py_is_gone() -> None:
    assert not pathlib.Path("harmony/api/routes/admin/internal.py").exists(), (
        "internal.py must be split into _safety.py, _crawler_sessions.py, _stats.py, _signals.py"
    )


def test_split_files_exist() -> None:
    base = pathlib.Path("harmony/api/routes/admin")
    for name in ("_safety.py", "_crawler_sessions.py", "_stats.py", "_signals.py"):
        assert (base / name).exists(), f"Missing {name}"
