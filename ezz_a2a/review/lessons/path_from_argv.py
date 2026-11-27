"""SonarCloud failed twice here: a command-line path that reaches a file read directly."""

import ast

ID = "path-from-argv"
NOTE = ("A command-line value reaches open/read_text/read_bytes without a lookup in an "
        "allowed listing. Verify the path cannot point outside the intended directory.")
READ_METHODS = {"open", "read_text", "read_bytes"}


def _command_line_names(tree) -> set[str]:
    return {target.id for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "parse_args"
            for target in node.targets if isinstance(target, ast.Name)}


def _from_command_line(node, namespaces: set[str], carried: set[str]) -> bool:
    if isinstance(node, ast.Call):
        return any(_from_command_line(argument, namespaces, carried) for argument in node.args)
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.value.id in namespaces
    return isinstance(node, ast.Name) and node.id in carried


def _carried_names(tree, namespaces: set[str]) -> set[str]:
    return {target.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
            and _from_command_line(node.value, namespaces, set())
            for target in node.targets if isinstance(target, ast.Name)}


def _is_read(node: ast.Call, namespaces: set[str], carried: set[str]) -> bool:
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        return any(_from_command_line(argument, namespaces, carried) for argument in node.args)
    return (isinstance(node.func, ast.Attribute) and node.func.attr in READ_METHODS
            and _from_command_line(node.func.value, namespaces, carried))


def check(source: dict) -> list[int]:
    try:
        tree = ast.parse(source["content"])
    except (SyntaxError, ValueError):
        return []
    namespaces = _command_line_names(tree)
    carried = _carried_names(tree, namespaces)
    return sorted({node.lineno for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and _is_read(node, namespaces, carried)})
