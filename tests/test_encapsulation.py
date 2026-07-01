from __future__ import annotations

import pathlib

ENCAPSULATED_PACKAGES = [
    "harmony/core",
    "harmony/api/services",
    "harmony/api/services/admin",
    "harmony/agents",
    "harmony/api/backends",
    "harmony/tools",
]

SKIP_FILES = {"__init__.py", "conftest.py", "ocr.py"}


def get_implementation_files(package_dir: pathlib.Path) -> list[pathlib.Path]:
    return [
        f
        for f in package_dir.glob("*.py")
        if f.name not in SKIP_FILES and not f.name.startswith("_")
    ]


def test_no_unencapsulated_implementation_files() -> None:
    violations: list[str] = []
    for pkg in ENCAPSULATED_PACKAGES:
        pkg_path = pathlib.Path(pkg)
        violations.extend(str(f) for f in get_implementation_files(pkg_path))
    assert not violations, (
        "These files should be renamed to _filename.py:\n" + "\n".join(violations)
    )
