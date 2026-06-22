#!/usr/bin/env python3
"""List every dataclass, pydantic.BaseModel, and TypedDict in the codebase.

Usage: python scripts/find_data_models.py [path]
"""

from __future__ import annotations

import argparse
import ast
import pathlib


def _decorator_names(decorators: list[ast.expr]) -> set[str]:
    names: set[str] = set()
    for dec in decorators:
        node = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _base_names(bases: list[ast.expr]) -> set[str]:
    names: set[str] = set()
    for base in bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def classify(node: ast.ClassDef) -> str | None:
    if "dataclass" in _decorator_names(node.decorator_list):
        return "dataclass"
    bases = _base_names(node.bases)
    if "BaseModel" in bases:
        return "pydantic.BaseModel"
    if "TypedDict" in bases:
        return "TypedDict"
    return None


def find_models(root: pathlib.Path) -> list[tuple[str, int, str, str]]:
    results: list[tuple[str, int, str, str]] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                kind = classify(node)
                if kind:
                    results.append((str(path), node.lineno, node.name, kind))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="harmony", help="Directory to scan")
    args = parser.parse_args()

    root = pathlib.Path(args.path)
    models = find_models(root)

    by_kind: dict[str, list[tuple[str, int, str, str]]] = {}
    for entry in models:
        by_kind.setdefault(entry[3], []).append(entry)

    for kind in sorted(by_kind):
        entries = by_kind[kind]
        print(f"\n{kind} ({len(entries)})")
        for filepath, lineno, name, _ in entries:
            print(f"  {filepath}:{lineno} {name}")

    print(f"\nTotal: {len(models)}")


if __name__ == "__main__":
    main()
