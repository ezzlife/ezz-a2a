"""A path read from the command line is how SonarCloud's security rating has failed twice.

Every argument typed as Path is listed here on purpose. Adding one fails this test
until someone decides it is safe, for example by looking the name up in a directory
listing as `ezz_a2a.review.measure` does.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEWED_PATH_ARGUMENTS = {
    ("ezz_a2a/client/cli.py", "task_file"),
    ("ezz_a2a/review/cli.py", "task_file"),
    ("ezz_a2a/review/cli.py", "--repository"),
    ("ezz_a2a/review/cli.py", "--output"),
}


def _is_path_argument(node: ast.Call) -> bool:
    return (isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
            and any(keyword.arg == "type" and isinstance(keyword.value, ast.Name)
                    and keyword.value.id == "Path" for keyword in node.keywords))


def _path_arguments(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and _is_path_argument(node):
            yield path.relative_to(PROJECT_ROOT).as_posix(), node.args[0].value


def test_every_command_line_path_argument_was_reviewed():
    found = {argument for path in (PROJECT_ROOT / "ezz_a2a").rglob("*.py")
             for argument in _path_arguments(path)}
    assert found == REVIEWED_PATH_ARGUMENTS


def test_the_scan_sees_a_path_argument():
    source = ast.parse("parser.add_argument('--x', type=Path)").body[0].value
    assert _is_path_argument(source)
