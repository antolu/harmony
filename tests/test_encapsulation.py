from __future__ import annotations

import ast
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


def test_no_self_absolute_import() -> None:
    harmony_dir = pathlib.Path("harmony")
    violations: list[str] = []

    for top_level_pkg in harmony_dir.iterdir():
        if not top_level_pkg.is_dir() or top_level_pkg.name in {
            "scripts",
            "__pycache__",
        }:
            continue

        pkg_name = top_level_pkg.name

        for py_file in top_level_pkg.rglob("*.py"):
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8"), filename=str(py_file)
                )
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.level == 0:
                        parts = node.module.split(".")
                        if (
                            len(parts) >= 2
                            and parts[0] == "harmony"
                            and parts[1] == pkg_name
                        ):
                            violations.append(
                                f"{py_file}:{node.lineno}: from {node.module} import ..."
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if (
                            len(parts) >= 2
                            and parts[0] == "harmony"
                            and parts[1] == pkg_name
                        ):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )

    assert not violations, "Self-package absolute imports found:\n" + "\n".join(
        violations
    )
