"""The scorer counts known real findings found and known false findings flagged."""

import json
from pathlib import Path

import pytest

from ezz_a2a.review.scoring import load_expected, score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FILE = PROJECT_ROOT / "cases/records-known-findings/expected.json"

EXPECTED = {
    "real": [
        {"id": "R2", "anchors": [["include_last_message"], ["no such column"]]},
        {"id": "R1", "anchors": [["wildcard|escape"]]},
    ],
    "false": [
        {"id": "F1", "anchors": [["order_by"], ["inject"]]},
    ],
}


def test_counts_real_and_false_findings_by_anchor():
    text = (
        "## Medium\n\n"
        "**M1. `include_last_message=False` fails.**\n- no such column: messages.content.\n\n"
        "**M2. LIKE wildcards are not escaped.**\n- `_` matches anything.\n\n"
        "**M3. `ORDER BY {order_by}` is injectable.**\n- It is an f-string.\n"
    )
    result = score(text, EXPECTED)
    assert result.real_found == ["R2", "R1"]
    assert result.false_flagged == ["F1"]
    assert (result.real_total, result.false_total) == (2, 1)


def test_anchors_must_appear_in_the_same_finding():
    text = (
        "**A. `include_last_message` is read here.**\n- Nothing wrong.\n\n"
        "**B. A no such column error is logged elsewhere.**\n- Unrelated.\n"
    )
    assert score(text, EXPECTED).real_found == []


def test_a_claim_under_a_no_defect_heading_is_not_a_finding():
    text = (
        "## Checked, no defect found\n\n"
        "**`ORDER BY {order_by}` looks injectable.**\n- It is one of two literals.\n"
    )
    assert score(text, EXPECTED).false_flagged == []


def test_matching_ignores_case():
    assert score("**UNESCAPED LIKE WILDCARDS**", EXPECTED).real_found == ["R1"]


def test_case_file_lists_five_real_and_three_false_findings():
    expected = load_expected(EXPECTED_FILE)
    assert [entry["id"] for entry in expected["real"]] == ["R1", "R2", "R3", "R4", "R5"]
    assert [entry["id"] for entry in expected["false"]] == ["F1", "F2", "F3"]
    assert all(entry["file"] and entry["lines"] for entry in expected["real"])


CASE_FINDINGS = {
    "R1": "**Open-ended slices crash.**\n- `rows[2:]` compares `len(self) < key.stop` with None: TypeError.",
    "R2": "**`Database.query` closes its connection too early.**\n- The RecordCollection is lazy, "
          "so the rows are read after the `with` block exits.",
    "R3": "**`transaction()` swallows errors.**\n- The bare except rolls back and never re-raises.",
    "R4": "**Binary exports are corrupted.**\n- `print(rows.export('xls'))` writes the b'...' repr.",
    "R5": "**The CLI never checks the format.**\n- `supported_formats` is unused, so `lang=python` "
          "becomes the format.",
    "F1": "**SQL injection in `Connection.query`.**\n- `text(query)` runs whatever string it gets.",
    "F2": "**StopIteration escapes `__iter__`.**\n- Under PEP 479 it becomes a RuntimeError.",
    "F3": "**`one()` only checks the first row.**\n- A second row is never looked at.",
}


RECORDED_RUNS = sorted((PROJECT_ROOT / "evidence").glob("records-known-findings-run-*.json"))


@pytest.mark.parametrize("run", RECORDED_RUNS, ids=lambda path: path.stem)
def test_each_recorded_run_finds_all_five_real_and_no_false_findings(run):
    evidence = json.loads(run.read_text(encoding="utf-8"))
    text = evidence["responses"][0]["artifacts"][0]["parts"][0]["text"]
    result = score(text, load_expected(EXPECTED_FILE))
    assert (result.real_found, result.false_flagged) == (["R1", "R2", "R3", "R4", "R5"], [])


def test_three_runs_are_recorded():
    assert len(RECORDED_RUNS) == 3


@pytest.mark.parametrize("finding_id", CASE_FINDINGS)
def test_each_case_anchor_matches_only_its_own_finding(finding_id):
    result = score(CASE_FINDINGS[finding_id], load_expected(EXPECTED_FILE))
    assert result.real_found + result.false_flagged == [finding_id]
