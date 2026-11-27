from pathlib import Path

MAX_LINES_PER_FILE = 300
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = ("ezz_a2a", "tests")


def test_no_python_file_exceeds_the_line_limit():
    oversized = {}
    for directory in SOURCE_DIRECTORIES:
        for path in (PROJECT_ROOT / directory).rglob("*.py"):
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > MAX_LINES_PER_FILE:
                oversized[str(path.relative_to(PROJECT_ROOT))] = line_count
    assert not oversized
