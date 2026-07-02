from __future__ import annotations

import pathlib

ENCAPSULATED_PACKAGES = [
    "harmony/core",
    "harmony/services",
    "harmony/services/admin",
    "harmony/agents",
    "harmony/agents/foa",
    "harmony/agents/simple",
    "harmony/api/routes",
    "harmony/api/routes/admin",
    "harmony/api/auth",
    "harmony/providers/web_crawler/auth",
    "harmony/providers/web_crawler/runtime",
    "harmony/providers/web_crawler/runtime/spiders",
    "harmony/models",
    "harmony/infrastructure/search",
    "harmony/tools",
]

SKIP_FILES = {"__init__.py", "conftest.py", "ocr.py", "settings.py"}


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
