"""Attach the definitions a reviewed Python file imports from files outside the review."""

import ast
import json
from pathlib import Path
from typing import Callable

PYTHON_SUFFIX = ".py"
PACKAGE_MODULE = "__init__.py"
DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _parse(text: str):
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def _module_candidates(source_path: str, node: ast.ImportFrom) -> list[Path]:
    base = Path(source_path).parent if node.level else Path()
    for _ in range(max(node.level - 1, 0)):
        base = base.parent
    module = base.joinpath(*node.module.split(".")) if node.module else base
    return [module.with_suffix(PYTHON_SUFFIX), module / PACKAGE_MODULE]


def _definition_names(node) -> list[str]:
    if isinstance(node, DEFINITION_NODES):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _first_line(node) -> int:
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno, *(decorator.lineno for decorator in decorators)])


def _find_definition(tree, lines: list[str], symbol: str) -> dict | None:
    for node in tree.body:
        if symbol in _definition_names(node):
            start, end = _first_line(node), node.end_lineno
            return {"lines": f"{start}-{end}", "content": "\n".join(lines[start - 1:end])}
    return None


def _read_module(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    tree = _parse(text)
    return None if tree is None else (tree, text.splitlines())


def _find_module(source_path: str, node: ast.ImportFrom, resolve: Callable[[str], Path]):
    for candidate in _module_candidates(source_path, node):
        try:
            path = resolve(candidate.as_posix())
        except ValueError:
            continue
        if path.is_file():
            return candidate.as_posix(), path
    return None


def build_definitions(sources: list[dict], resolve: Callable[[str], Path]) -> list[dict]:
    """Definitions of used imported symbols whose file is not one of the listed sources."""
    listed = {resolve(source["path"]) for source in sources}
    definitions: dict[tuple[str, str], dict] = {}
    for source in sources:
        tree = _parse(source["content"]) if source["path"].endswith(PYTHON_SUFFIX) else None
        if tree is None:
            continue
        used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = _find_module(source["path"], node, resolve)
            if module is None or module[1] in listed:
                continue
            parsed = _read_module(module[1])
            if parsed is None:
                continue
            module_tree, module_lines = parsed
            for alias in node.names:
                key = (module[0], alias.name)
                if alias.name == "*" or (alias.asname or alias.name) not in used:
                    continue
                found = _find_definition(module_tree, module_lines, alias.name)
                if found and key not in definitions:
                    definitions[key] = {"symbol": alias.name, "path": module[0], **found}
    return list(definitions.values())


def fit(entries: list[dict], fits: Callable[[list[dict]], bool]) -> list[dict]:
    """Drop the longest entries until the whole prompt fits."""
    kept = list(entries)
    while kept and not fits(kept):
        kept.remove(max(kept, key=lambda entry: len(json.dumps(entry))))
    return kept
