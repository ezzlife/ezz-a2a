"""Each lesson is a deterministic detector for a defect a review found once."""

from pathlib import Path

import pytest

from ezz_a2a.review.lessons import find_hits
from ezz_a2a.review.lessons import like_without_escape, order_by_without_tiebreaker, path_from_argv

CASE_SOURCE = Path(__file__).resolve().parents[2] / "cases/records-known-findings/source/records.py"


def lines_of(lesson, text):
    return lesson.check({"path": "sample", "content": text})


@pytest.mark.parametrize("text", [
    'sql = "SELECT 1 WHERE name LIKE ?"',
    'return f"{col} LIKE ?"',
    'return f"norm({col}) LIKE norm(?)"',
    "SELECT 1 WHERE name LIKE :pattern",
    "SELECT 1 WHERE name LIKE %s",
])
def test_like_with_an_input_pattern_and_no_escape_is_a_hit(text):
    assert lines_of(like_without_escape, text) == [1]


@pytest.mark.parametrize("text", [
    "SELECT 1 WHERE name LIKE ? ESCAPE '\\'",
    "SELECT 1 WHERE name LIKE ?\n  ESCAPE '\\'",
    "SELECT 1 WHERE jid LIKE '%@lid'",
    "name = ?",
])
def test_like_that_escapes_or_uses_a_literal_is_not_a_hit(text):
    assert lines_of(like_without_escape, text) == []


@pytest.mark.parametrize("text,line", [
    ('sql += f" ORDER BY {order_col} {order} LIMIT ? OFFSET ?"', 1),
    ("SELECT * FROM t ORDER BY created_at DESC LIMIT ? OFFSET ?", 1),
    ("SELECT * FROM t\nORDER BY m.timestamp\nLIMIT 10 OFFSET 20", 2),
])
def test_paginated_order_by_on_one_column_is_a_hit(text, line):
    assert lines_of(order_by_without_tiebreaker, text) == [line]


@pytest.mark.parametrize("text", [
    "SELECT * FROM t ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
    "SELECT * FROM t ORDER BY id LIMIT ? OFFSET ?",
    "SELECT * FROM t ORDER BY m.rowid DESC LIMIT ? OFFSET ?",
    "SELECT * FROM t ORDER BY created_at DESC LIMIT ?",
    "SELECT * FROM t ORDER BY created_at",
])
def test_unique_tiebreaker_or_no_pagination_is_not_a_hit(text):
    assert lines_of(order_by_without_tiebreaker, text) == []


ARGV_READS = [
    "args = parser.parse_args()\nopen(args.name)",
    "args = parser.parse_args()\nPath(args.name).read_text()",
    "args = parser.parse_args()\nargs.name.read_bytes()",
    "args = parser.parse_args()\ntarget = args.name\ntarget.open()",
]


@pytest.mark.parametrize("text", ARGV_READS)
def test_a_path_from_argv_reaching_a_read_is_a_hit(text):
    assert lines_of(path_from_argv, text) == [text.count("\n") + 1]


@pytest.mark.parametrize("text", [
    "args = parser.parse_args()\nprepare(args.name)",
    "name = 'fixed'\nopen(name)",
    "def broken(:",
])
def test_argv_values_that_are_not_read_directly_are_not_a_hit(text):
    assert lines_of(path_from_argv, text) == []


def test_hits_carry_lesson_path_line_and_note():
    source = {"path": "db/text.py", "content": 'x = 1\nsql = "WHERE a LIKE ?"'}
    hits = find_hits([source])
    assert hits == [{"lesson": "like-without-escape", "path": "db/text.py", "line": 2,
                     "note": like_without_escape.NOTE}]


def test_the_case_source_has_no_lesson_hits_so_the_prompt_adds_no_false_leads():
    source = {"path": "records.py", "content": CASE_SOURCE.read_text(encoding="utf-8")}
    assert find_hits([source]) == []
